import { useCities } from '@/entities/city'
import type { City } from '@/shared/types'
import type { FormEvent } from 'react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import './TownsPage.css'

const CITIES_PER_PAGE = 15;
const MAP_ZOOM = 11;

const buildPreviewUrl = (city: City) => {
    const { c_longitude, c_latitude } = city.property;
    return `https://static-maps.yandex.ru/1.x/?lang=en-US&ll=${c_longitude},${c_latitude}&size=450,450&z=${MAP_ZOOM}&l=map`;
};

export const TownsPage = () => {
    const [search, setSearch] = useState('');
    const [displayCount, setDisplayCount] = useState(CITIES_PER_PAGE);

    const { data: allCities = [], isFetching, isLoading, error } = useCities(0, 1000);
    const filteredCities = useMemo(() => {
        if (!search.trim()) return allCities;

        const lower = search.trim().toLowerCase();
        return allCities.filter((city) => city.city_name.toLowerCase().includes(lower));
    }, [allCities, search]);

    const displayedCities = filteredCities.slice(0, displayCount);

    const hasMore = displayCount < filteredCities.length;

    const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
    };

    const handleLoadMore = () => {
        setDisplayCount((prev) => prev + CITIES_PER_PAGE);
    };

    const handleSearchChange = (value: string) => {
        setSearch(value);
        setDisplayCount(CITIES_PER_PAGE);
    };

    return (
        <div className="towns-layout">
            <form className="towns-search" onSubmit={handleSubmit} role="search">
                <input
                    type="search"
                    placeholder="Поиск"
                    value={search}
                    onChange={(event) => handleSearchChange(event.target.value)}
                    aria-label="Поиск города"
                />
                <button type="submit" title="Найти город">
                    <span className="material-symbols-outlined" aria-hidden="true">
                        search
                    </span>
                    <span className="sr-only">Поиск</span>
                </button>
            </form>

            {error && (
                <div className="towns-error">
                    Не удалось загрузить города. Попробуйте обновить страницу.
                </div>
            )}

            {isLoading ? (
                <div className="towns-loading">Загрузка городов...</div>
            ) : (
                <>
                    <div className="towns-list" aria-live="polite">
                        {displayedCities.map((city) => (
                            <Link key={city.id} to={`/towns/${city.id}`} className="town-card">
                                <div className="town-card__image" aria-hidden="true">
                                    <img src={buildPreviewUrl(city)} alt="" loading="lazy" />
                                </div>
                                <div className="town-card__content">
                                    <h2>{city.city_name}</h2>
                                </div>
                                <div
                                    className="town-card__download"
                                    title={city.downloaded ? 'Город скачан' : 'Город не скачан'}
                                >
                                    <span
                                        className="material-symbols-outlined"
                                        style={{
                                            color: city.downloaded
                                                ? '#6abcff'
                                                : 'rgba(105, 105, 105, 0.478)',
                                        }}
                                        aria-hidden="true"
                                    >
                                        download
                                    </span>
                                </div>
                            </Link>
                        ))}
                    </div>

                    {hasMore && (
                        <div className="towns-actions">
                            <button
                                type="button"
                                onClick={handleLoadMore}
                                disabled={isFetching}
                                className="load-more-button"
                            >
                                {isFetching ? (
                                    <>
                                        <span className="spinner"></span>
                                        Загрузка...
                                    </>
                                ) : (
                                    <>Показать ещё</>
                                )}
                            </button>
                        </div>
                    )}

                    {!hasMore && displayedCities.length > 0 && (
                        <div className="towns-end-message">
                            {search
                                ? `Найдено городов: ${filteredCities.length}`
                                : `Показаны все города (${allCities.length})`}
                        </div>
                    )}

                    {displayedCities.length === 0 && !isLoading && search && (
                        <div className="towns-empty">
                            По запросу "{search}" ничего не найдено
                        </div>
                    )}
                </>
            )}
        </div>
    );
};