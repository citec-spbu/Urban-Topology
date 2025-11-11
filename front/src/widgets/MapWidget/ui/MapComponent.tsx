import type { Region } from '@/shared/types'
import type { LatLngTuple } from 'leaflet'
import React, { useEffect } from 'react'
import { MapContainer, Polygon, Popup, TileLayer, useMap } from 'react-leaflet'

interface MapComponentProps {
    center: LatLngTuple;
    regions: Region[][];
    onGraphInfo: (params: { name: string; regionId?: number; polygon?: [number, number][] }) => void;
    isActive?: boolean;
}

const getPolygonCoords = (region: Region): LatLngTuple[][] => {
    return region.regions.map(
        (ring: [number, number][]) => ring.map(([lon, lat]: [number, number]) => [lat, lon] as LatLngTuple)
    );
};

const RegionPolygons: React.FC<{
    regions: Region[][];
    onGraphInfo: (params: { name: string; regionId?: number }) => void;
}> = ({ regions, onGraphInfo }) => {
    if (!regions.length) return null;
    return (
        <>
            {regions.map((level) =>
                level.map((region) => (
                    <Polygon
                        key={region.id}
                        positions={getPolygonCoords(region)}
                        pathOptions={{ color: '#830000', fillOpacity: 0.1 }}
                        eventHandlers={{
                            click: () => onGraphInfo({ name: region.name, regionId: region.id }),
                        }}
                    >
                        <Popup>
                            <b>{region.name}</b>
                            <br />ID: {region.id}
                        </Popup>
                    </Polygon>
                ))
            )}
        </>
    );
};

const MapResizer: React.FC<{ active?: boolean }> = ({ active }) => {
    const map = useMap();

    useEffect(() => {
        if (active) {
            const timeout = window.setTimeout(() => {
                map.invalidateSize();
            }, 50);
            return () => window.clearTimeout(timeout);
        }
    }, [active, map]);

    useEffect(() => {
        const handleResize = () => map.invalidateSize();
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, [map]);

    return null;
};

export const MapComponent: React.FC<MapComponentProps> = ({ center, regions, onGraphInfo, isActive }) => {
    return (
        <MapContainer
            center={center}
            zoom={10}
            scrollWheelZoom
            className="leaflet-map"
            style={{ height: '100%', width: '100%' }}
        >
            <MapResizer active={isActive} />
            <TileLayer
                attribution='&copy; OpenStreetMap contributors'
                url='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
            />
            <RegionPolygons regions={regions} onGraphInfo={onGraphInfo} />
        </MapContainer>
    );
};
