import { useTown, useTownSection } from '@/entities/city'
import { useGraphLoader, useGraphState } from '@/entities/graph'
import { MapComponent } from '@/widgets/MapWidget'
import { RoadsComponent } from '@/widgets/RoadsWidget'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import './TownPage.css'

export const TownPage = () => {
    const { id } = useParams<{ id: string }>();
    const { town, isLoading: isTownLoading, error: townError } = useTown(id ?? '');
    const { isMapActive, isRoadsActive, showMap, showRoads } = useTownSection();
    const { loadGraph, isLoading: isGraphLoading } = useGraphLoader();
    const { graphData, setGraphData, setAreaName, hasGraph } = useGraphState();
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    const handleGraphLoad = async (params: { name: string; regionId?: number; polygon?: any }) => {
        if (!id) return;

        setAreaName(params.name);
        setErrorMessage(null);

        try {
            const data = await loadGraph({
                cityId: Number(id),
                regionId: params.regionId,
                polygon: params.polygon,
            });
            setGraphData(data);
            showRoads();
        } catch (error: any) {
            const message = error?.response?.data?.detail || error.message || 'Неизвестная ошибка при загрузке графа.';
            setErrorMessage(message);
            console.error('Ошибка загрузки графа:', error);
        }
    };

    const handleDownload = () => {
        console.log('Запрос на скачивание CSV...');
        alert('Функционал скачивания будет реализован позже.');
    };

    if (isTownLoading) {
        return <div className="town-page-loading">Загрузка информации о городе...</div>;
    }

    if (townError) {
        return <div className="town-page-error">Ошибка: {townError.message}</div>;
    }

    const isLoading = isTownLoading || isGraphLoading;

    return (
        <div className={`town-page-wrapper ${isLoading ? 'loading' : ''}`}>
            <div className={`map-wrapper ${isMapActive ? '' : 'is-hidden'}`}>
                <a id="map-section" />
                {town && (
                    <MapComponent
                        center={[town.property.c_latitude, town.property.c_longitude]}
                        regions={town.districts}
                        onGraphInfo={handleGraphLoad}
                        isActive={isMapActive}
                    />
                )}
            </div>

            <div className={`roads-wrapper ${isRoadsActive ? '' : 'is-hidden'}`}>
                <a id="roads-section" />
                <RoadsComponent graphData={graphData} onDownload={handleDownload} isActive={isRoadsActive} />
            </div>

            <nav className="town-page-nav">
                <button title="Карта" className={isMapActive ? 'active' : ''} onClick={showMap}>
                    Карта
                </button>
                <button title="Дороги" className={isRoadsActive ? 'active' : ''} onClick={showRoads} disabled={!hasGraph}>
                    Дороги
                </button>
            </nav>

            {isLoading && (
                <div className="town-page-overlay">
                    <div className="loader"></div>
                </div>
            )}

            {errorMessage && (
                <div className="error-notification">
                    <div className="error-content">
                        <span className="error-icon">⚠️</span>
                        <span className="error-text">{errorMessage}</span>
                        <button className="error-close" onClick={() => setErrorMessage(null)} title="Закрыть">✕</button>
                    </div>
                </div>
            )}
        </div>
    );
};
