import { useCities } from '@/entities/city'
import type { City } from '@/shared/types'
import type { FormEvent } from 'react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import './TownsPage.css'

const DEFAULT_PER_PAGE = 15;
const MAP_ZOOM = 10;

const buildPreviewUrl = (city: City) => {
    const { c_longitude, c_latitude } = city.property;
    return `https://static-maps.yandex.ru/1.x/?lang=en-US&ll=${c_longitude},${c_latitude}&size=450,450&z=${MAP_ZOOM}&l=map`;
};

export const TownsPage = () => {
    const [page, setPage] = useState(0);
    const [perPage] = useState(DEFAULT_PER_PAGE);
    const [search, setSearch] = useState('');
    const [cities, setCities] = useState<City[]>([]);
    const [noMoreCities, setNoMoreCities] = useState(false);

    const { data, isFetching, isLoading, error } = useCities(page, perPage);

    useEffect(() => {
        if (!data) return;

        setCities((prev) => {
            const next = page === 0 ? [] : [...prev];
            const indexById = new Map(next.map((city) => [city.id, city] as const));

            data.forEach((city) => {
                indexById.set(city.id, city);
            });

            return Array.from(indexById.values());
        });

        setNoMoreCities(data.length < perPage);
    }, [data, page, perPage]);

    useEffect(() => {
        if (page > 0 && error) {
            console.error('Не удалось загрузить список городов:', error);
        }
    }, [page, error]);

    const filteredCities = useMemo(() => {
        if (!search.trim()) return cities;

        const lower = search.trim().toLowerCase();
        return cities.filter((city) => city.city_name.toLowerCase().includes(lower));
    }, [cities, search]);

    const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
    };

    const handleLoadMore = () => {
        if (isFetching || noMoreCities) return;
        setPage((prev) => prev + 1);
    };

    return (
        <div className="towns-layout">
            <form className="towns-search" onSubmit={handleSubmit} role="search">
                <input
                    type="search"
                    placeholder="Поиск"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    aria-label="Поиск города"
                />
                <button type="submit" title="Найти город">
                    <span className="material-symbols-outlined" aria-hidden="true">
                        search
                    </span>
                    <span className="sr-only">Поиск</span>
                </button>
            </form>

            {error && cities.length === 0 && (
                <div className="towns-error">Не удалось загрузить города. Попробуйте обновить страницу.</div>
            )}

            <div className="towns-list" aria-live="polite">
                {filteredCities.map((city) => (
                    <Link key={city.id} to={`/towns/${city.id}`} className="town-card">
                        <div className="town-card__image" aria-hidden="true">
                            <img src={buildPreviewUrl(city)} alt="" loading="lazy" />
                        </div>
                        <div className="town-card__content">
                            <h2>{city.city_name}</h2>
                        </div>
                        <div className="town-card__download" title={city.downloaded ? 'Город скачан' : 'Город не скачан'}>
                            <span
                                className="material-symbols-outlined"
                                style={{ color: city.downloaded ? '#6abcff' : 'rgba(105, 105, 105, 0.478)' }}
                                aria-hidden="true"
                            >
                                download
                            </span>
                        </div>
                    </Link>
                ))}
            </div>

            {!noMoreCities && (
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
            
            {noMoreCities && cities.length > 0 && (
                <div className="towns-end-message">
                    Показаны все города ({filteredCities.length})
                </div>
            )}

            {isLoading && cities.length === 0 && (
                <div className="towns-loading">Загрузка...</div>
            )}
        </div>
    );

};
