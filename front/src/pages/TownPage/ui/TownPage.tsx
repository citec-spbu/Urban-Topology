import {citiesApi, useTown, useTownSection} from '@/entities/city'
import {useGraphLoader, useGraphState} from '@/entities/graph'
import {MapComponent} from '@/widgets/MapWidget'
import {RoadsComponent} from '@/widgets/RoadsWidget'
import {useState} from 'react'
import {useParams} from 'react-router-dom'

export const TownPage = () => {
    const {id} = useParams<{ id: string }>();
    const {town, isLoading: isTownLoading, error: townError} = useTown(id ?? '');
    const {isMapActive, isRoadsActive, showMap, showRoads} = useTownSection();
    const {loadGraph, isLoading: isGraphLoading} = useGraphLoader();
    const {graphData, setGraphData, setAreaName, areaName, hasGraph} = useGraphState();
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [lastRequest, setLastRequest] = useState<{ regionId?: number; polygon?: [number, number][] } | null>(null);
    const [isDownloading, setIsDownloading] = useState(false);

    const handleGraphLoad = async (params: { name: string; regionId?: number; polygon?: [number, number][] }) => {
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
            setLastRequest({ regionId: params.regionId, polygon: params.polygon });
            showRoads();
        } catch (error: unknown) {
            const err = error as { response?: { data?: { detail?: string } }, message?: string };
            const message = err?.response?.data?.detail || err?.message || 'Неизвестная ошибка при загрузке графа.';
            setErrorMessage(message);
            console.error('Ошибка загрузки графа:', error);
        }
    };

    const handleDownload = async () => {
        if (!id) return;
        if (!graphData) {
            setErrorMessage('Сначала загрузите граф для выбранного района.');
            return;
        }
        if (!lastRequest?.regionId) {
            setErrorMessage('Выберите район на карте и дождитесь завершения загрузки графа.');
            return;
        }
        if (lastRequest.polygon) {
            setErrorMessage('Скачивание пока доступно только для районов.');
            return;
        }

        try {
            setIsDownloading(true);
            const blob = await citiesApi.downloadGraphExport(Number(id), [lastRequest.regionId]);
            const safeArea = areaName?.trim() || '';
            const slug = safeArea
                .toLowerCase()
                .replace(/\s+/g, '-')
                .replace(/[^a-z0-9а-яё_-]/gi, '') || `region-${lastRequest.regionId}`;
            const fileName = `city-${id}-${slug}.zip`;
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = fileName;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);
        } catch (error: unknown) {
            const err = error as { response?: { data?: { detail?: string } }, message?: string };
            const message = err?.response?.data?.detail || err?.message || 'Не удалось скачать архив с графом.';
            setErrorMessage(message);
            console.error('Ошибка скачивания CSV:', error);
        } finally {
            setIsDownloading(false);
        }
    };

    if (isTownLoading) {
        return (
            <div className="flex justify-center items-center h-screen text-lg">
                Загрузка информации о городе...
            </div>
        );
    }

    if (townError) {
        return (
            <div className="flex justify-center items-center h-screen text-lg text-red-700">
                Ошибка: {townError.message}
            </div>
        );
    }

    const isLoading = isTownLoading || isGraphLoading;

    return (
        <div
            className={`overflow-hidden relative w-full bg-white h-[calc(100vh-48px)]${isLoading ? ' pointer-events-none cursor-not-allowed' : ''}`}>
            <div className={`${isMapActive ? 'flex' : 'hidden'} h-[calc(100vh-48px)] w-full flex-1 min-w-0`}>
                <a id="map-section"/>
                {town && (
                    <MapComponent
                        center={[town.property.c_latitude, town.property.c_longitude]}
                        regions={town.districts}
                        onGraphInfo={handleGraphLoad}
                        isActive={isMapActive}
                    />
                )}
            </div>

            <div className={`${isRoadsActive ? 'flex' : 'hidden'} h-[calc(100vh-48px)] w-full flex-1 min-w-0`}>
                <a id="roads-section"/>
                <RoadsComponent
                    graphData={graphData}
                    onDownload={handleDownload}
                    isActive={isRoadsActive}
                    isDownloading={isDownloading}
                />
            </div>

            <nav className="fixed top-[45vh] left-4 z-[999] flex flex-col gap-2">
                <button
                    title="Карта"
                    className={`px-4 py-2 border border-[#008cff] bg-[#6abcff80] text-black rounded transition-all text-sm ${isMapActive ? 'bg-[#6abcff] font-bold' : ''} hover:bg-[#6abcff]`}
                    onClick={showMap}
                >
                    Карта
                </button>
                <button
                    title="Дороги"
                    className={`px-4 py-2 border border-[#008cff] bg-[#6abcff80] text-black rounded transition-all text-sm ${isRoadsActive ? 'bg-[#6abcff] font-bold' : ''} hover:bg-[#6abcff] disabled:border-gray-400 disabled:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-60`}
                    onClick={showRoads}
                    disabled={!hasGraph}
                >
                    Дороги
                </button>
            </nav>

            {(isLoading || isDownloading) && (
                <div className="fixed inset-0 flex justify-center items-center z-[999] backdrop-blur-sm">
                    <div className="border-4 border-gray-200 border-t-[#008cff] rounded-full w-12 h-12 animate-spin"/>
                </div>
            )}

            {errorMessage && (
                <div className="fixed top-20 right-5 z-[1000] max-w-[400px] animate-slide-in">
                    <div className="flex items-center gap-3 p-4 bg-white border-2 border-red-700 rounded-lg shadow-lg">
                        <span className="text-2xl flex-shrink-0">⚠️</span>
                        <span className="flex-1 text-red-700 text-sm">{errorMessage}</span>
                        <button
                            className="bg-none border-none text-xl cursor-pointer px-2 text-gray-500 hover:text-red-700"
                            onClick={() => setErrorMessage(null)}
                            title="Закрыть"
                        >✕
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};