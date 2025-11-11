import type { GraphData } from '@/shared/types'
import type { LatLngBoundsExpression } from 'leaflet'
import React, { useEffect, useMemo } from 'react'
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, useMap } from 'react-leaflet'
import './RoadsComponent.css'

interface RoadsComponentProps {
    graphData: GraphData | null;
    onDownload: () => void;
    isActive?: boolean;
}

const getNodeLatLng = (node: any) => [node.lat, node.lon] as [number, number];

const parseCSV = (csv?: string): Record<string, string>[] => {
    const trimmed = (csv || '').trim();
    if (!trimmed) return [];

    const [headerLine, ...lines] = trimmed.split(/\r?\n/);
    if (!headerLine) return [];

    const headers = headerLine.split(',');
    return lines
        .filter(Boolean)
        .map((line) => {
            const values = line.split(',');
            return headers.reduce<Record<string, string>>((acc, header, index) => {
                acc[header] = (values[index] ?? '').trim();
                return acc;
            }, {});
        });
};

const hasCsvGraphData = (
    data: GraphData | null,
): data is GraphData & { edges_csv: string; points_csv: string } => {
    return (
        !!data &&
        typeof (data as any).edges_csv === 'string' &&
        typeof (data as any).points_csv === 'string'
    );
};

const toNumber = (value?: string): number | undefined => {
    if (value === undefined || value === null || value === '') return undefined;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
};

const computeBounds = (nodes: Record<string, any>): LatLngBoundsExpression | null => {
    const entries = Object.values(nodes);
    if (!entries.length) return null;

    let minLat = Infinity;
    let maxLat = -Infinity;
    let minLon = Infinity;
    let maxLon = -Infinity;

    entries.forEach((node: any) => {
        const [lat, lon] = getNodeLatLng(node);
        if (lat < minLat) minLat = lat;
        if (lat > maxLat) maxLat = lat;
        if (lon < minLon) minLon = lon;
        if (lon > maxLon) maxLon = lon;
    });

    if (!Number.isFinite(minLat) || !Number.isFinite(minLon) || !Number.isFinite(maxLat) || !Number.isFinite(maxLon)) {
        return null;
    }

    if (minLat === maxLat && minLon === maxLon) {
        const delta = 0.001;
        return [
            [minLat - delta, minLon - delta],
            [maxLat + delta, maxLon + delta],
        ];
    }

    return [
        [minLat, minLon],
        [maxLat, maxLon],
    ];
};

const MapResizer: React.FC<{ active?: boolean; bounds?: LatLngBoundsExpression | null }> = ({ active, bounds }) => {
    const map = useMap();

    useEffect(() => {
        if (active) {
            const timeout = window.setTimeout(() => map.invalidateSize(), 50);
            return () => window.clearTimeout(timeout);
        }
    }, [active, map]);

    useEffect(() => {
        if (active && bounds) {
            map.fitBounds(bounds, { padding: [40, 40], maxZoom: 17 });
        }
    }, [active, bounds, map]);

    useEffect(() => {
        const handleResize = () => map.invalidateSize();
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, [map]);

    return null;
};

export const RoadsComponent: React.FC<RoadsComponentProps> = ({ graphData, onDownload, isActive }) => {
    if (import.meta.env.DEV) {
        console.log('graphData:', graphData);
    }

    let nodes: Record<string, any> = {};
    let edges: any[] = [];
    
    if (hasCsvGraphData(graphData)) {
        const metricRows = parseCSV((graphData as any).metrics_csv);
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
            const lon = toNumber(row.longitude || row.long || row.longtitude);
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
                from: row.source || row.from || row.id_src,
                to: row.target || row.to || row.id_dist,
                name: row.name,
            }))
            .filter((edge) => edge.from && edge.to);
    } else if (graphData && typeof graphData === 'object') {
        nodes = graphData.nodes && typeof graphData.nodes === 'object' ? graphData.nodes : {};
        const edgesObj = graphData.edges && typeof graphData.edges === 'object' ? graphData.edges : {};
        edges = Object.values(edgesObj ?? {});
    }

    const safeNodes: Record<string, any> = (nodes && typeof nodes === 'object' && !Array.isArray(nodes)) ? nodes : {};
    const firstNode = Object.values(safeNodes)[0];
    const center: [number, number] = firstNode && getNodeLatLng(firstNode).length === 2
        ? getNodeLatLng(firstNode) as [number, number]
        : [55.75, 37.61];

    const bounds = useMemo(() => computeBounds(safeNodes), [safeNodes]);

    if (!safeNodes || Object.keys(safeNodes).length === 0 || !edges || edges.length === 0) {
        return <div className="roads-placeholder">Нет данных для отображения графа.</div>;
    }

    return (
        <div className="roads-map-wrapper">
            <MapContainer
                center={center}
                zoom={12}
                scrollWheelZoom
                className="leaflet-map"
                style={{ height: '100%', width: '100%', flex: 1 }}
            >
                <MapResizer active={isActive} bounds={bounds} />
                <TileLayer
                    attribution='&copy; OpenStreetMap contributors'
                    url='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
                />
                {edges.map((edge: any, idx: number) => {
                    if (!edge) return null;
                    const fromId = edge.from || edge.source || edge.n1;
                    const toId = edge.to || edge.target || edge.n2;
                    const from = safeNodes[fromId];
                    const to = safeNodes[toId];
                    if (!from || !to) return null;
                    return (
                        <Polyline
                            key={edge.id || idx}
                            positions={[getNodeLatLng(from), getNodeLatLng(to)]}
                            pathOptions={{ color: '#85818c', weight: 4 }}
                        />
                    );
                })}
                {Object.entries(safeNodes).map(([id, node]: [string, any]) => (
                    <CircleMarker
                        key={id}
                        center={getNodeLatLng(node)}
                        radius={Number(node.radius_value) || 5}
                        pathOptions={{ color: node.color_value || '#008cff', fillColor: node.color_value || '#008cff', fillOpacity: 0.8 }}
                    >
                        <Popup>
                            <b>Перекрёсток</b><br />
                            ID: {id}<br />
                            Degree: {node.degree_value}<br />
                            In-Degree: {node.in_degree_value}<br />
                            Out-Degree: {node.out_degree_value}<br />
                            Eigenvector: {node.eigenvector_value}<br />
                            Betweenness: {node.betweenness_value}<br />
                        </Popup>
                    </CircleMarker>
                ))}
            </MapContainer>
            <div className="roads-panel">
                <button onClick={onDownload} className="roads-download-btn">Скачать CSV</button>
            </div>
        </div>
    );
};
