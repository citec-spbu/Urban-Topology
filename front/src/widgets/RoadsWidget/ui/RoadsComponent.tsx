import type {GraphData} from '@/shared/types'
import type {LatLngBoundsExpression} from 'leaflet'
import React, {useEffect, useMemo} from 'react'
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

interface RoadsComponentProps {
    graphData: GraphData | null
    onDownload: () => void
    isActive?: boolean
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

const parseCSV = (csv?: string): Record<string, string>[] => {
    const trimmed = (csv || '').trim()
    if (!trimmed) return []
    const [headerLine, ...lines] = trimmed.split(/\r?\n/)
    if (!headerLine) return []
    const headers = headerLine.split(',')
    return lines
        .filter(Boolean)
        .map((line) => {
            const values = line.split(',')
            return headers.reduce<Record<string, string>>((acc, header, index) => {
                acc[header] = (values[index] ?? '').trim()
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

const toNumber = (value?: string): number | undefined => {
    if (value === undefined || value === null || value === '') return undefined
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : undefined
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
            const timeout = window.setTimeout(() => map.invalidateSize(), 50)
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

export const RoadsComponent: React.FC<RoadsComponentProps> = ({graphData, onDownload, isActive}) => {
    let nodes: Record<string, Node> = {}
    let edges: Edge[] = []

    if (hasCsvGraphData(graphData)) {
        const metricRows = parseCSV(graphData.metrics_csv);
        const metricsById = metricRows.reduce<Record<string, Record<string, string>>>((acc, row) => {
            const id = row.id?.trim();
            if (id) acc[id] = row;
            return acc;
        }, {});

        const pointRows = parseCSV(graphData.points_csv);
        pointRows.forEach((row) => {
            const id = row.id?.trim();
            if (!id) return;

            const lat = toNumber(row.latitude || row.lat || row.latitude_value);
            const lon = toNumber(row.longitude || row.long || row.longitude_value || row.longtitude);
            if (lat === undefined || lon === undefined) return;

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
            };
        });

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

    const safeNodes: Record<string, Node> = (nodes && typeof nodes === 'object' && !Array.isArray(nodes)) ? nodes : {}
    const firstNode = Object.values(safeNodes)[0]
    const center: [number, number] = firstNode && getNodeLatLng(firstNode).length === 2
        ? getNodeLatLng(firstNode)
        : [55.75, 37.61]

    const bounds = useMemo(() => computeBounds(safeNodes), [safeNodes])

    if (!safeNodes || Object.keys(safeNodes).length === 0 || !edges || edges.length === 0) {
        return <div className="p-8 text-center text-gray-500 w-full min-w-0">Нет данных для отображения графа.</div>
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
                {edges.map((edge, idx) => {
                    const from = safeNodes[edge.from]
                    const to = safeNodes[edge.to]
                    if (!from || !to) return null
                    return (
                        <Polyline
                            key={edge.id || idx}
                            positions={[getNodeLatLng(from), getNodeLatLng(to)]}
                            pathOptions={{color: '#85818c', weight: 4}}
                        />
                    )
                })}
                {Object.entries(safeNodes).map(([id, node]) => (
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
            </MapContainer>
            <div className="absolute bottom-5 right-5 z-[1200]">
                <button
                    onClick={onDownload}
                    className="px-5 py-2 bg-blue-700 hover:bg-blue-800 active:bg-blue-900 text-white rounded shadow transition font-medium"
                >
                    Скачать CSV
                </button>
            </div>
        </div>
    )
}