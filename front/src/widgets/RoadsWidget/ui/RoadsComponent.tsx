import type {GraphData} from '@/shared/types'
import type {LatLngBoundsExpression} from 'leaflet'
import React, {useEffect, useMemo, useState} from 'react'
import {CircleMarker, MapContainer, Polyline, Popup, TileLayer, useMap} from 'react-leaflet'

interface Node {
    lat: number
    lon: number
    layer?: string
    node_type?: string
    way_id?: string
    degree_value?: string
    in_degree_value?: string
    out_degree_value?: string
    eigenvector_value?: string
    betweenness_value?: string
    radius_value?: string
    color_value?: string
    source_type?: string
    source_id?: string
    name?: string
}

interface Edge {
    id?: string
    way_id?: string
    from: string
    to: string
    name?: string
    layer?: string
    source_way_id?: string
    road_type?: string
    length_m?: string
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

const hasMetricData = (node: Node): boolean => {
    return [
        node.degree_value,
        node.in_degree_value,
        node.out_degree_value,
        node.eigenvector_value,
        node.betweenness_value,
    ].some((value) => value !== undefined && value !== '')
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
    const [showPedestrian, setShowPedestrian] = useState(false)
    
    let nodes: Record<string, Node> = {}
    let edges: Edge[] = []
    let invalidPointRows = 0

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
            const layer = row.layer?.trim() || 'base';
            const nodeType = row.node_type?.trim() || '';

            nodes[id] = {
                lat,
                lon,
                layer,
                node_type: nodeType,
                way_id: '',
                degree_value: metric.degree,
                in_degree_value: metric.in_degree,
                out_degree_value: metric.out_degree,
                eigenvector_value: metric.eigenvector,
                betweenness_value: metric.betweenness,
                radius_value: metric.radius,
                color_value: metric.color,
                source_type: row.source_type?.trim(),
                source_id: row.source_id?.trim(),
                name: row.name?.trim(),
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
            .map((row) => {
                const layer = row.layer?.trim() || 'base';
                return {
                    id: row.id,
                    way_id: row.id_way || row.way_id,
                    from: row.source || row.from || row.id_src || '',
                    to: row.target || row.to || row.id_dist || '',
                    name: row.name,
                    layer,
                    source_way_id: row.source_way_id,
                    road_type: row.road_type,
                    length_m: row.length_m,
                    isBuildingLink: parseBool(row.is_building_link),
                };
            })
            .filter((edge) => edge.from && edge.to);
    } else if (graphData && typeof graphData === 'object') {
        nodes = graphData.nodes && typeof graphData.nodes === 'object' ? graphData.nodes as Record<string, Node> : {}
        const edgesObj = graphData.edges && typeof graphData.edges === 'object' ? graphData.edges : {}
        edges = Object.values(edgesObj ?? {}) as Edge[]
    }

    const safeNodes: Record<string, Node> = (nodes && typeof nodes === 'object' && !Array.isArray(nodes)) ? nodes : {}
    const firstNode = Object.values(safeNodes)[0]
    const center: [number, number] = firstNode && getNodeLatLng(firstNode).length === 2
        ? getNodeLatLng(firstNode)
        : [55.75, 37.61]

    const bounds = useMemo(() => {
        const merged: Record<string, Node> = {}
        
        Object.entries(safeNodes).forEach(([id, node]) => {
            const layer = node.layer || 'base';
            if (layer === 'base' && showRoads) {
                merged[id] = node;
            } else if (layer === 'access' && node.node_type === 'building' && showBuildings) {
                merged[id] = node;
            } else if (layer === 'access' && node.node_type !== 'building' && showPedestrian) {
                merged[id] = node;
            }
        });
        
        if (!Object.keys(merged).length) {
            return computeBounds(safeNodes)
        }
        return computeBounds(merged)
    }, [safeNodes, showRoads, showBuildings, showPedestrian])

    const baseNodes = Object.values(safeNodes).filter(n => (n.layer || 'base') === 'base');
    const buildingNodes = Object.values(safeNodes).filter(n => n.layer === 'access' && n.node_type === 'building');
    const pedestrianNodes = Object.values(safeNodes).filter(n => n.layer === 'access' && n.node_type !== 'building');
    
    const baseEdges = edges.filter(e => (e.layer || 'base') === 'base');
    const pedestrianEdges = edges.filter(e => e.layer === 'access');
    
    const hasMainGraph = baseNodes.length > 0 && baseEdges.length > 0;
    const hasBuildingsLayer = buildingNodes.length > 0;
    const hasPedestrianLayer = pedestrianEdges.length > 0;
    
    const canDownload = Boolean(graphData) && (hasMainGraph || hasBuildingsLayer || hasPedestrianLayer);

    useEffect(() => {
        if (!hasBuildingsLayer && showBuildings) {
            setShowBuildings(false)
        }
    }, [hasBuildingsLayer, showBuildings])

    useEffect(() => {
        if (!hasPedestrianLayer && showPedestrian) {
            setShowPedestrian(false)
        }
    }, [hasPedestrianLayer, showPedestrian])

    useEffect(() => {
        if (!hasMainGraph && showRoads) {
            setShowRoads(false)
        }
    }, [hasMainGraph, showRoads])

    if (!hasMainGraph && !hasBuildingsLayer && !hasPedestrianLayer) {
        return (
            <div className="p-8 text-center text-gray-500 space-y-2">
                <div>Нет данных для отображения графа.</div>
                {invalidPointRows > 0 && (
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
                {showRoads && baseEdges.map((edge, idx) => {
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
                {showPedestrian && pedestrianEdges.map((edge, idx) => {
                    const from = safeNodes[edge.from]
                    const to = safeNodes[edge.to]
                    if (!from || !to) return null
                    return (
                        <Polyline
                            key={`pedestrian-${edge.id || idx}`}
                            positions={[getNodeLatLng(from), getNodeLatLng(to)]}
                            pathOptions={{
                                color: edge.isBuildingLink ? '#16a34a' : '#f97316',
                                weight: edge.isBuildingLink ? 3 : 4,
                                opacity: 0.9,
                            }}
                        />
                    )
                })}
                {showRoads && baseNodes.map((node) => (
                    <CircleMarker
                        key={node.way_id || Math.random()}
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
                                Degree: {node.degree_value}<br/>
                                In-Degree: {node.in_degree_value}<br/>
                                Out-Degree: {node.out_degree_value}<br/>
                                Eigenvector: {node.eigenvector_value}<br/>
                                Betweenness: {node.betweenness_value}<br/>
                            </div>
                        </Popup>
                    </CircleMarker>
                ))}
                {showBuildings && buildingNodes.map((node) => (
                    <CircleMarker
                        key={`building-${node.source_id || Math.random()}`}
                        center={getNodeLatLng(node)}
                        radius={6}
                        pathOptions={{
                            color: '#16a34a',
                            fillColor: '#16a34a',
                            fillOpacity: 0.85,
                        }}
                    >
                        <Popup>
                            <div className="text-sm">
                                <b>Здание</b><br/>
                                Источник: {node.source_type} {node.source_id}<br/>
                                {node.name ? <>Название: {node.name}<br/></> : null}
                                {hasMetricData(node) ? (
                                    <>
                                        Degree: {node.degree_value}<br/>
                                        In-Degree: {node.in_degree_value}<br/>
                                        Out-Degree: {node.out_degree_value}<br/>
                                        Eigenvector: {node.eigenvector_value}<br/>
                                        Betweenness: {node.betweenness_value}<br/>
                                    </>
                                ) : null}
                            </div>
                        </Popup>
                    </CircleMarker>
                ))}
                {showPedestrian && pedestrianNodes.map((node) => (
                    <CircleMarker
                        key={`pedestrian-node-${node.source_id || Math.random()}`}
                        center={getNodeLatLng(node)}
                        radius={Number(node.radius_value) || 4}
                        pathOptions={{
                            color: node.color_value || '#f97316',
                            fillColor: node.color_value || '#f97316',
                            fillOpacity: 0.85,
                        }}
                    >
                        <Popup>
                            <div className="text-sm">
                                <b>Точка доступа</b><br/>
                                Источник: {node.source_type} {node.source_id}<br/>
                                {node.name ? <>Название: {node.name}<br/></> : null}
                                {hasMetricData(node) ? (
                                    <>
                                        Degree: {node.degree_value}<br/>
                                        In-Degree: {node.in_degree_value}<br/>
                                        Out-Degree: {node.out_degree_value}<br/>
                                        Eigenvector: {node.eigenvector_value}<br/>
                                        Betweenness: {node.betweenness_value}<br/>
                                    </>
                                ) : null}
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
                <label className={`flex items-center gap-2 text-sm ${!hasBuildingsLayer ? 'opacity-50' : ''}`}>
                    <input
                        type="checkbox"
                        checked={showBuildings}
                        disabled={!hasBuildingsLayer}
                        onChange={(e) => setShowBuildings(e.target.checked)}
                    />
                    Здания
                </label>
                <label className={`flex items-center gap-2 text-sm ${!hasPedestrianLayer ? 'opacity-50' : ''}`}>
                    <input
                        type="checkbox"
                        checked={showPedestrian}
                        disabled={!hasPedestrianLayer}
                        onChange={(e) => setShowPedestrian(e.target.checked)}
                    />
                    Пешеходные связи
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