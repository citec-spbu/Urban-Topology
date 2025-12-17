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
    layer?: string  // 'base' или 'access'
    node_type?: string  // 'graph', 'building' и т.д.
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
    layer?: string  // 'base' или 'access'
    is_building_link?: boolean
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
    const [showPedestrianLinks, setShowPedestrianLinks] = useState(false)
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
                layer: row.layer,
                node_type: row.node_type,
                source_type: row.source_type,
                source_id: row.source_id,
                name: row.name,
            }
        })
        if (invalidPointRows) {
            console.warn('Пропущены узлы из-за некорректных координат', {
                skipped: invalidPointRows,
                examples: invalidNodeSamples,
            })
        }
        
        console.log('Total nodes parsed:', Object.keys(nodes).length);

        const edgeRows = parseCSV(graphData.edges_csv);
        console.log('Parsed edge rows:', edgeRows.length);
        
        const mappedEdges = edgeRows.map((row) => ({
            id: row.id,
            way_id: row.id_way || row.way_id,
            from: row.source || row.from || row.id_src || '',
            to: row.target || row.to || row.id_dist || '',
            name: row.name,
            layer: row.layer,
            is_building_link: parseBool(row.is_building_link),
        }));
        
        const edgesWithoutEndpoints = mappedEdges.filter(e => !e.from || !e.to);
        if (edgesWithoutEndpoints.length > 0) {
            console.warn('Edges without from/to:', edgesWithoutEndpoints.length, edgesWithoutEndpoints.slice(0, 3));
        }
        
        edges = mappedEdges.filter((edge) => edge.from && edge.to);
        
        console.log('Edges after filtering (from && to):', edges.length);
    } else if (graphData && typeof graphData === 'object') {
        nodes = graphData.nodes && typeof graphData.nodes === 'object' ? graphData.nodes as Record<string, Node> : {}
        const edgesObj = graphData.edges && typeof graphData.edges === 'object' ? graphData.edges : {}
        edges = Object.values(edgesObj ?? {}) as Edge[]
    }

    // Note: with unified format, access_nodes_csv and access_edges_csv are now null
    // All data (base + access) is merged into points_csv and edges_csv with layer metadata

    const safeNodes: Record<string, Node> = (nodes && typeof nodes === 'object' && !Array.isArray(nodes)) ? nodes : {}
    
    // Разделяем узлы по слоям
    const roadNodes = Object.entries(safeNodes).reduce((acc, [id, node]) => {
        if (node.layer === 'access') return acc
        acc[id] = node
        return acc
    }, {} as Record<string, Node>)
    
    const buildingNodes = Object.entries(safeNodes).reduce((acc, [id, node]) => {
        if (node.layer !== 'access' || node.node_type !== 'building') return acc
        acc[id] = node
        return acc
    }, {} as Record<string, Node>)
    
    // Разделяем рёбра по слоям
    const roadEdges = edges.filter(e => e.layer !== 'access')
    const buildingEdges = edges.filter(e => e.layer === 'access' && !e.is_building_link)
    const pedestrianEdges = edges.filter(e => e.layer === 'access' && e.is_building_link)
    
    console.log('Edge counts:', {
        total: edges.length,
        road: roadEdges.length,
        building: buildingEdges.length,
        pedestrian: pedestrianEdges.length,
        accessTotal: edges.filter(e => e.layer === 'access').length,
        sampleAccessEdge: edges.find(e => e.layer === 'access'),
        sampleBuildingEdge: buildingEdges[0],
        samplePedestrianEdge: pedestrianEdges[0],
    })
    
    // Debug: проверяем есть ли узлы для access рёбер
    if (buildingEdges.length > 0) {
        const firstBuildingEdge = buildingEdges[0]
        const fromNode = buildingNodes[firstBuildingEdge.from] || roadNodes[firstBuildingEdge.from]
        const toNode = buildingNodes[firstBuildingEdge.to] || roadNodes[firstBuildingEdge.to]
        console.log('Building edge lookup:', {
            edge: firstBuildingEdge,
            fromNode: fromNode ? 'found' : 'MISSING',
            toNode: toNode ? 'found' : 'MISSING',
            totalBuildingNodes: Object.keys(buildingNodes).length,
            totalRoadNodes: Object.keys(roadNodes).length,
        })
    }
    
    const firstNode = Object.values(roadNodes)[0] || Object.values(buildingNodes)[0]
    const center: [number, number] = firstNode && getNodeLatLng(firstNode).length === 2
        ? getNodeLatLng(firstNode)
        : [55.75, 37.61]

    const bounds = useMemo(() => {
        const merged: Record<string, Node> = {}
        if (showRoads) {
            Object.entries(roadNodes).forEach(([id, node]) => {
                merged[id] = node
            })
        }
        if (showBuildings) {
            Object.entries(buildingNodes).forEach(([id, node]) => {
                merged[id] = node
            })
        }
        if (showPedestrianLinks && showBuildings) {
            Object.entries(buildingNodes).forEach(([id, node]) => {
                merged[`ped-${id}`] = {lat: node.lat, lon: node.lon, way_id: ''}
            })
        }
        if (!Object.keys(merged).length) {
            return computeBounds(roadNodes)
        }
        return computeBounds(merged)
    }, [roadNodes, buildingNodes, showRoads, showBuildings, showPedestrianLinks])

    const hasRoadData = Object.keys(roadNodes).length > 0 || roadEdges.length > 0
    const hasBuildingData = Object.keys(buildingNodes).length > 0 || buildingEdges.length > 0
    const hasPedestrianData = pedestrianEdges.length > 0
    const displayRoads = showRoads && hasRoadData
    const displayBuildings = showBuildings && hasBuildingData
    const displayPedestrian = showPedestrianLinks && hasPedestrianData && showBuildings
    const canDownload = Boolean(graphData) && (hasRoadData || hasBuildingData)

    useEffect(() => {
        if (!hasBuildingData && showBuildings) {
            setShowBuildings(false)
        }
    }, [hasBuildingData, showBuildings])

    useEffect(() => {
        if (!hasRoadData && showRoads) {
            setShowRoads(false)
        }
    }, [hasRoadData, showRoads])

    useEffect(() => {
        if (!hasPedestrianData && showPedestrianLinks) {
            setShowPedestrianLinks(false)
        }
    }, [hasPedestrianData, showPedestrianLinks])

    if (!hasRoadData && !hasBuildingData) {
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
                {/* Дороги (base layer edges) */}
                {displayRoads && roadEdges.map((edge, idx) => {
                    const from = roadNodes[edge.from]
                    const to = roadNodes[edge.to]
                    if (!from || !to) return null
                    return (
                        <Polyline
                            key={`road-${edge.id || idx}`}
                            positions={[getNodeLatLng(from), getNodeLatLng(to)]}
                            pathOptions={{color: '#64748b', weight: 3, opacity: 0.8}}
                        />
                    )
                })}
                
                {/* Связи зданий (access layer edges, not building links) */}
                {displayBuildings && buildingEdges.map((edge, idx) => {
                    const from = buildingNodes[edge.from] || roadNodes[edge.from]
                    const to = buildingNodes[edge.to] || roadNodes[edge.to]
                    if (!from || !to) return null
                    return (
                        <Polyline
                            key={`building-${edge.id || idx}`}
                            positions={[getNodeLatLng(from), getNodeLatLng(to)]}
                            pathOptions={{color: '#ea580c', weight: 2, opacity: 0.7, dashArray: '5, 5'}}
                        />
                    )
                })}
                
                {/* Пешеходные связи (building links) */}
                {displayPedestrian && pedestrianEdges.map((edge, idx) => {
                    const from = buildingNodes[edge.from] || roadNodes[edge.from]
                    const to = roadNodes[edge.to] || buildingNodes[edge.to]
                    if (!from || !to) return null
                    return (
                        <Polyline
                            key={`pedestrian-${edge.id || idx}`}
                            positions={[getNodeLatLng(from), getNodeLatLng(to)]}
                            pathOptions={{color: '#f59e0b', weight: 2, opacity: 0.8}}
                        />
                    )
                })}
                
                {/* Узлы дорог (base layer nodes) */}
                {displayRoads && Object.entries(roadNodes).map(([id, node]) => (
                    <CircleMarker
                        key={id}
                        center={getNodeLatLng(node)}
                        radius={Number(node.radius_value) || 4}
                        pathOptions={{
                            color: node.color_value || '#0ea5e9',
                            fillColor: node.color_value || '#0ea5e9',
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
                
                {/* Здания (access layer nodes) */}
                {displayBuildings && Object.entries(buildingNodes).map(([id, node]) => (
                    <CircleMarker
                        key={`building-${id}`}
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
                                ID: {id}<br/>
                                Источник: {node.source_type} {node.source_id}<br/>
                                {node.name ? <>Название: {node.name}<br/></> : null}
                            </div>
                        </Popup>
                    </CircleMarker>
                ))}
            </MapContainer>
            <div
                className="absolute top-5 right-5 w-56 bg-white rounded shadow p-4 space-y-3 border border-gray-200 z-[1200] pointer-events-auto"
            >
                <div className="text-sm font-semibold text-gray-700">Слои карты</div>
                <label className={`flex items-center gap-2 text-sm ${!hasRoadData ? 'opacity-50' : ''}`}>
                    <input
                        type="checkbox"
                        checked={showRoads}
                        disabled={!hasRoadData}
                        onChange={(e) => setShowRoads(e.target.checked)}
                    />
                    <span className="flex-1">Дороги</span>
                    <span className="inline-block w-3 h-3 bg-sky-400 rounded"></span>
                </label>
                <label className={`flex items-center gap-2 text-sm ${!hasBuildingData ? 'opacity-50' : ''}`}>
                    <input
                        type="checkbox"
                        checked={showBuildings}
                        disabled={!hasBuildingData}
                        onChange={(e) => setShowBuildings(e.target.checked)}
                    />
                    <span className="flex-1">Здания</span>
                    <span className="inline-block w-3 h-3 bg-amber-400 rounded"></span>
                </label>
                <label className={`flex items-center gap-2 text-sm ${!hasPedestrianData || !showBuildings ? 'opacity-50' : ''}`}>
                    <input
                        type="checkbox"
                        checked={showPedestrianLinks}
                        disabled={!hasPedestrianData || !showBuildings}
                        onChange={(e) => setShowPedestrianLinks(e.target.checked)}
                    />
                    <span className="flex-1">Пешеходные связи</span>
                    <span className="inline-block w-3 h-3 bg-green-500 rounded"></span>
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