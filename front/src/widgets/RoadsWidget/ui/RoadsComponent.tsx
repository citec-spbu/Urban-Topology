import type {GraphData} from '@/shared/types'
import type {LatLngBoundsExpression} from 'leaflet'
import React, {useEffect, useMemo, useState} from 'react'
import {CircleMarker, MapContainer, Polyline, Popup, TileLayer, useMap} from 'react-leaflet'

interface Node {
    lat: number
    lon: number
    way_id?: string
    degree_value?: string
    in_degree_value?: string
    out_degree_value?: string
    eigenvector_value?: string
    betweenness_value?: string
    radius_value?: string
    color_value?: string
}

interface Edge {
    id?: string
    way_id?: string
    from: string
    to: string
    name?: string
}

interface AccessNode {
    lat: number
    lon: number
    node_type: string
    source_type?: string
    source_id?: string
    name?: string
}

interface AccessEdge {
    id?: string
    from: string
    to: string
    road_type?: string
    name?: string
    isBuildingLink?: boolean
}

interface RoadsComponentProps {
    graphData: GraphData | null
    onDownload: () => void | Promise<void>
    isActive?: boolean
    isDownloading?: boolean
}

const getNodeLatLng = (node: Node): [number, number] => [node.lat, node.lon]

const RemoveLeafletPrefix: React.FC = () => {
    const map = useMap();

    useEffect(() => {
        if (map?.attributionControl) {
            map.attributionControl.setPrefix('');
        }
    }, [map]);

    return null;
};

// Minimal CSV parser that keeps quoted values intact (e.g. rgb colors with commas).
const parseCsvLine = (line: string): string[] => {
    const result: string[] = []
    let current = ''
    let inQuotes = false
    const sanitized = line.replace(/\r$/, '')

    for (let i = 0; i < sanitized.length; i += 1) {
        const char = sanitized[i]

        if (char === '"') {
            if (inQuotes && sanitized[i + 1] === '"') {
                current += '"'
                i += 1
            } else {
                inQuotes = !inQuotes
            }
            continue
        }

        if (char === ',' && !inQuotes) {
            result.push(current)
            current = ''
            continue
        }

        current += char
    }

    result.push(current)
    return result
}

const cleanCsvValue = (value?: string): string => {
    if (value === undefined) return ''
    let trimmed = value.replace(/^[\ufeff\u2060]/, '').trim()
    if (trimmed.startsWith('"') && trimmed.endsWith('"')) {
        trimmed = trimmed.slice(1, -1).replace(/""/g, '"')
    }
    return trimmed.replace(/[\u00a0\u202f]/g, ' ')
}

const parseCSV = (csv?: string): Record<string, string>[] => {
    const trimmed = (csv || '').trim()
    if (!trimmed) return []
    const [headerLine, ...lines] = trimmed.split(/\r?\n/)
    if (!headerLine) return []
    const headers = parseCsvLine(headerLine).map((header) => cleanCsvValue(header).toLowerCase())
    return lines
        .filter(Boolean)
        .map((line) => {
            const values = parseCsvLine(line)
            return headers.reduce<Record<string, string>>((acc, header, index) => {
                acc[header] = cleanCsvValue(values[index])
                return acc
            }, {})
        })
}

const hasCsvGraphData = (
    data: GraphData | null,
): data is GraphData & { edges_csv: string; points_csv: string; metrics_csv: string } => {
    return (
        !!data &&
        typeof (data as Record<string, unknown>).edges_csv === 'string' &&
        typeof (data as Record<string, unknown>).points_csv === 'string'
    );
};

const normalizeNumberString = (value: string): string => {
    return value
        .replace(/\ufeff/g, '')
        .replace(/[\u00a0\u202f]/g, '')
        .replace(/,/g, '.')
        .trim()
}

const toNumber = (value?: string): number | undefined => {
    if (value === undefined || value === null) return undefined
    const normalized = normalizeNumberString(value)
    if (!normalized) return undefined
    const parsed = Number(normalized)
    return Number.isFinite(parsed) ? parsed : undefined
}

const parseBool = (value?: string): boolean => {
    if (value === undefined || value === null) return false
    const normalized = value.trim().toLowerCase()
    return normalized === 'true' || normalized === '1' || normalized === 'yes'
}

const computeBounds = (nodes: Record<string, Node>): LatLngBoundsExpression | null => {
    const entries = Object.values(nodes)
    if (!entries.length) return null

    let minLat = Infinity
    let maxLat = -Infinity
    let minLon = Infinity
    let maxLon = -Infinity

    entries.forEach((node) => {
        const [lat, lon] = getNodeLatLng(node)
        if (lat < minLat) minLat = lat
        if (lat > maxLat) maxLat = lat
        if (lon < minLon) minLon = lon
        if (lon > maxLon) maxLon = lon
    })

    if (!Number.isFinite(minLat) || !Number.isFinite(minLon) || !Number.isFinite(maxLat) || !Number.isFinite(maxLon)) {
        return null
    }

    if (minLat === maxLat && minLon === maxLon) {
        const delta = 0.001
        return [
            [minLat - delta, minLon - delta],
            [maxLat + delta, maxLon + delta],
        ]
    }

    return [
        [minLat, minLon],
        [maxLat, maxLon],
    ]
}

const MapResizer: React.FC<{ active?: boolean; bounds?: LatLngBoundsExpression | null }> = ({active, bounds}) => {
    const map = useMap()

    useEffect(() => {
        if (active) {
            const timeout = window.setTimeout(() => {
                map.invalidateSize()
            }, 50)
            return () => window.clearTimeout(timeout)
        }
    }, [active, map])

    useEffect(() => {
        if (active && bounds) {
            map.fitBounds(bounds, {padding: [40, 40], maxZoom: 17})
        }
    }, [active, bounds, map])

    useEffect(() => {
        const handleResize = () => map.invalidateSize()
        window.addEventListener('resize', handleResize)
        return () => window.removeEventListener('resize', handleResize)
    }, [map])

    return null
}

export const RoadsComponent: React.FC<RoadsComponentProps> = ({graphData, onDownload, isActive, isDownloading}) => {
    const [showRoads, setShowRoads] = useState(true)
    const [showBuildings, setShowBuildings] = useState(false)
    let nodes: Record<string, Node> = {}
    let edges: Edge[] = []
    let accessNodes: Record<string, AccessNode> = {}
    let accessEdges: AccessEdge[] = []
    let invalidPointRows = 0
    let invalidAccessRows = 0

    if (hasCsvGraphData(graphData)) {
        const metricRows = parseCSV(graphData.metrics_csv);
        const metricsById = metricRows.reduce<Record<string, Record<string, string>>>((acc, row) => {
            const id = row.id?.trim();
            if (id) acc[id] = row;
            return acc;
        }, {});

        const pointRows = parseCSV(graphData.points_csv)
        const invalidNodeSamples: string[] = []
        pointRows.forEach((row) => {
            const id = row.id?.trim();
            if (!id) return;

            const lat = toNumber(row.latitude || row.lat || row.latitude_value)
            const lon = toNumber(row.longitude || row.long || row.longitude_value || row.longtitude)
            if (lat === undefined || lon === undefined) {
                invalidPointRows += 1
                if (invalidNodeSamples.length < 5) {
                    invalidNodeSamples.push(id || JSON.stringify(row))
                }
                return
            }

            const metric = metricsById[id] ?? {};

            nodes[id] = {
                lat,
                lon,
                way_id: '',
                degree_value: metric.degree,
                in_degree_value: metric.in_degree,
                out_degree_value: metric.out_degree,
                eigenvector_value: metric.eigenvector,
                betweenness_value: metric.betweenness,
                radius_value: metric.radius,
                color_value: metric.color,
            }
        })
        if (invalidPointRows) {
            console.warn('Пропущены узлы из-за некорректных координат', {
                skipped: invalidPointRows,
                examples: invalidNodeSamples,
            })
        }

        const edgeRows = parseCSV(graphData.edges_csv);
        edges = edgeRows
            .map((row) => ({
                id: row.id,
                way_id: row.id_way || row.way_id,
                from: row.source || row.from || row.id_src || '',
                to: row.target || row.to || row.id_dist || '',
                name: row.name,
            }))
            .filter((edge) => edge.from && edge.to);
    } else if (graphData && typeof graphData === 'object') {
        nodes = graphData.nodes && typeof graphData.nodes === 'object' ? graphData.nodes as Record<string, Node> : {}
        const edgesObj = graphData.edges && typeof graphData.edges === 'object' ? graphData.edges : {}
        edges = Object.values(edgesObj ?? {}) as Edge[]
    }

    if (graphData && typeof graphData === 'object') {
        if (typeof (graphData as any).access_nodes_csv === 'string') {
            const accessNodeRows = parseCSV((graphData as any).access_nodes_csv)
            const invalidAccessSamples: string[] = []
            accessNodeRows.forEach((row) => {
                const id = row.id?.trim()
                if (!id) return
                const lat = toNumber(row.latitude || row.lat)
                const lon = toNumber(row.longitude || row.lon)
                if (lat === undefined || lon === undefined) {
                    invalidAccessRows += 1
                    if (invalidAccessSamples.length < 5) {
                        invalidAccessSamples.push(id || JSON.stringify(row))
                    }
                    return
                }
                accessNodes[id] = {
                    lat,
                    lon,
                    node_type: row.node_type || 'intersection',
                    source_type: row.source_type,
                    source_id: row.source_id,
                    name: row.name,
                }
            })
            if (invalidAccessRows) {
                console.warn('Пропущены точки доступа из-за некорректных координат', {
                    skipped: invalidAccessRows,
                    examples: invalidAccessSamples,
                })
            }
        }

        if (typeof (graphData as any).access_edges_csv === 'string') {
            const accessEdgeRows = parseCSV((graphData as any).access_edges_csv)
            accessEdges = accessEdgeRows
                .map((row) => ({
                    id: row.id,
                    from: row.source || row.from || row.id_src || '',
                    to: row.target || row.to || row.id_dst || '',
                    road_type: row.road_type,
                    name: row.name,
                    isBuildingLink: parseBool(row.is_building_link),
                }))
                .filter((edge) => edge.from && edge.to)
        }
    }

    const safeNodes: Record<string, Node> = (nodes && typeof nodes === 'object' && !Array.isArray(nodes)) ? nodes : {}
    const firstNode = Object.values(safeNodes)[0]
    const firstAccessNode = Object.values(accessNodes)[0]
    const center: [number, number] = firstNode && getNodeLatLng(firstNode).length === 2
        ? getNodeLatLng(firstNode)
        : firstAccessNode
            ? [firstAccessNode.lat, firstAccessNode.lon]
            : [55.75, 37.61]

    const bounds = useMemo(() => {
        const merged: Record<string, Node> = {}
        if (showRoads) {
            Object.entries(safeNodes).forEach(([id, node]) => {
                merged[id] = node
            })
        }
        if (showBuildings) {
            Object.entries(accessNodes).forEach(([id, node]) => {
                merged[`access-${id}`] = {lat: node.lat, lon: node.lon, way_id: ''}
            })
        }
        if (!Object.keys(merged).length) {
            return computeBounds(safeNodes)
        }
        return computeBounds(merged)
    }, [safeNodes, accessNodes, showRoads, showBuildings])

    const nodeCount = safeNodes ? Object.keys(safeNodes).length : 0
    const hasMainGraph = nodeCount > 0 && edges && edges.length > 0
    const hasAccessGraph = accessNodes && Object.keys(accessNodes).length > 0 && accessEdges && accessEdges.length > 0
    const displayAccessGraph = showBuildings && hasAccessGraph
    const displayMainGraph = showRoads && hasMainGraph
    const canDownload = Boolean(graphData) && (hasMainGraph || hasAccessGraph)

    useEffect(() => {
        if (!hasAccessGraph && showBuildings) {
            setShowBuildings(false)
        }
    }, [hasAccessGraph, showBuildings])

    useEffect(() => {
        if (!hasMainGraph && showRoads) {
            setShowRoads(false)
        }
    }, [hasMainGraph, showRoads])

    if (!hasMainGraph && !hasAccessGraph) {
        return (
            <div className="p-8 text-center text-gray-500 space-y-2">
                <div>Нет данных для отображения графа.</div>
                {(invalidPointRows > 0 || invalidAccessRows > 0) && (
                    <div className="text-sm text-red-600">
                        Обнаружены строки с некорректными координатами. Проверьте исходные данные региона или повторите загрузку.
                    </div>
                )}
            </div>
        )
    }

    return (
        <div className="relative h-full w-full min-w-0 bg-white flex flex-col">
            <MapContainer
                center={center}
                zoom={12}
                scrollWheelZoom
                className="flex-1 min-h-[400px] rounded-lg shadow-lg"
                style={{height: '100%', width: '100%'}}
            >
                <RemoveLeafletPrefix />
                <MapResizer active={isActive} bounds={bounds}/>
                <TileLayer
                    attribution="&copy; OpenStreetMap contributors"
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                {displayMainGraph && edges.map((edge, idx) => {
                    const from = safeNodes[edge.from]
                    const to = safeNodes[edge.to]
                    if (!from || !to) return null
                    return (
                        <Polyline
                            key={`road-${edge.id || idx}`}
                            positions={[getNodeLatLng(from), getNodeLatLng(to)]}
                            pathOptions={{color: '#85818c', weight: 4}}
                        />
                    )
                })}
                {displayAccessGraph && accessEdges.map((edge, idx) => {
                    const from = accessNodes[edge.from]
                    const to = accessNodes[edge.to]
                    if (!from || !to) return null
                    return (
                        <Polyline
                            key={`access-${edge.id || idx}`}
                            positions={[[from.lat, from.lon], [to.lat, to.lon]]}
                            pathOptions={{
                                color: edge.isBuildingLink ? '#16a34a' : '#f97316',
                                weight: edge.isBuildingLink ? 3 : 4,
                                opacity: 0.9,
                            }}
                        />
                    )
                })}
                {displayMainGraph && Object.entries(safeNodes).map(([id, node]) => (
                    <CircleMarker
                        key={id}
                        center={getNodeLatLng(node)}
                        radius={Number(node.radius_value) || 5}
                        pathOptions={{
                            color: node.color_value || '#008cff',
                            fillColor: node.color_value || '#008cff',
                            fillOpacity: 0.8
                        }}
                    >
                        <Popup>
                            <div className="text-sm">
                                <b>Перекрёсток</b><br/>
                                ID: {id}<br/>
                                Degree: {node.degree_value}<br/>
                                In-Degree: {node.in_degree_value}<br/>
                                Out-Degree: {node.out_degree_value}<br/>
                                Eigenvector: {node.eigenvector_value}<br/>
                                Betweenness: {node.betweenness_value}<br/>
                            </div>
                        </Popup>
                    </CircleMarker>
                ))}
                {displayAccessGraph && Object.entries(accessNodes).map(([id, node]) => (
                    <CircleMarker
                        key={`access-node-${id}`}
                        center={[node.lat, node.lon]}
                        radius={node.node_type === 'building' ? 6 : 4}
                        pathOptions={{
                            color: node.node_type === 'building' ? '#16a34a' : '#f97316',
                            fillColor: node.node_type === 'building' ? '#16a34a' : '#f97316',
                            fillOpacity: 0.85,
                        }}
                    >
                        <Popup>
                            <div className="text-sm">
                                <b>{node.node_type === 'building' ? 'Здание' : 'Перекрёсток'}</b><br/>
                                ID: {id}<br/>
                                Источник: {node.source_type} {node.source_id}<br/>
                                {node.name ? <>Название: {node.name}<br/></> : null}
                            </div>
                        </Popup>
                    </CircleMarker>
                ))}
            </MapContainer>
            <div
                className="absolute top-5 right-5 w-52 bg-white rounded shadow p-3 space-y-2 border border-gray-200 z-[1200] pointer-events-auto"
            >
                <div className="text-sm font-semibold text-gray-700">Слои карты</div>
                <label className={`flex items-center gap-2 text-sm ${!hasMainGraph ? 'opacity-50' : ''}`}>
                    <input
                        type="checkbox"
                        checked={showRoads}
                        disabled={!hasMainGraph}
                        onChange={(e) => setShowRoads(e.target.checked)}
                    />
                    Дороги
                </label>
                <label className={`flex items-center gap-2 text-sm ${!hasAccessGraph ? 'opacity-50' : ''}`}>
                    <input
                        type="checkbox"
                        checked={showBuildings}
                        disabled={!hasAccessGraph}
                        onChange={(e) => setShowBuildings(e.target.checked)}
                    />
                    Здания и узлы
                </label>
            </div>
            <div className="absolute bottom-5 right-5 z-[1200] pointer-events-auto">
                <button
                    onClick={onDownload}
                    disabled={!canDownload || isDownloading}
                    className="px-5 py-2 bg-blue-700 hover:bg-blue-800 active:bg-blue-900 text-white rounded shadow transition font-medium disabled:opacity-60 disabled:cursor-not-allowed"
                >
                    {isDownloading ? 'Скачивание...' : 'Скачать CSV'}
                </button>
            </div>
			
        </div>
    )
}