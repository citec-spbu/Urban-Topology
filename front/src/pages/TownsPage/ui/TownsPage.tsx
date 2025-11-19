import {useCities} from '@/entities/city'
import type {City} from '@/shared/types'
import type {FormEvent} from 'react'
import {useMemo, useState} from 'react'
import {Link} from 'react-router-dom'

const CITIES_PER_PAGE = 15;
const MAX_CITIES_TO_FETCH = 1000;
const MAP_ZOOM = 11;

const buildPreviewUrl = (city: City) => {
    const {c_longitude, c_latitude} = city.property;
    return `https://static-maps.yandex.ru/1.x/?lang=en-US&ll=${c_longitude},${c_latitude}&size=450,450&z=${MAP_ZOOM}&l=map`;
};

function pluralizeCity(count: number) {
    if (count % 10 === 1 && count % 100 !== 11) return `Найден ${count} город`;
    if (
        [2, 3, 4].includes(count % 10) &&
        ![12, 13, 14].includes(count % 100)
    )
        return `Найдено ${count} города`;
    return `Найдено ${count} городов`;
}

export const TownsPage = () => {
    const [search, setSearch] = useState('');
    const [displayCount, setDisplayCount] = useState(CITIES_PER_PAGE);

    const {data: allCities = [], isLoading, error} = useCities(0, MAX_CITIES_TO_FETCH);
    const filteredCities = useMemo(() => {
        if (!search.trim()) return allCities;

        const lower = search.trim().toLowerCase();
        return allCities.filter((city) =>
            city.city_name.toLowerCase().startsWith(lower));
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

    if (error) {
        return (
            <div className="text-center py-10 px-5 text-[1.1rem] text-[#d32f2f]">
                Не удалось загрузить города. Попробуйте обновить страницу.
            </div>
        );
    }

    return (
        <div className="flex flex-col gap-4 p-6 max-w-[1200px] mx-auto">
            <form className="flex items-center justify-center w-full py-3 bg-transparent" onSubmit={handleSubmit}
                  role="search">
                <div
                    className="relative flex items-center w-full max-w-[600px] bg-white/80 rounded-full px-4 py-2 border border-[rgba(200,199,196,0.2)] transition-all duration-200 focus-within:border-blue-400 focus-within:shadow-md">
                    <span className="material-symbols-outlined text-[#6b6a67] text-[20px] mr-3 flex-shrink-0"
                          aria-hidden="true">
                        search
                    </span>
                    <input
                        type="search"
                        name="city-search"
                        placeholder="Введите название города"
                        value={search}
                        onChange={(event) => handleSearchChange(event.target.value)}
                        aria-label="Введите название города"
                        className="flex-1 border-none outline-none text-[16px] bg-transparent p-0 text-[#2a2927] placeholder:text-[#9a9996]"
                    />
                </div>
            </form>

            {isLoading ? (
                <div className="text-center py-10 px-5 text-[1.1rem]">Загрузка городов...</div>
            ) : (
                <>
                    <div className="flex flex-wrap justify-center gap-8 w-full mx-auto" aria-live="polite">
                        {displayedCities.map((city) => (
                            <Link
                                key={city.id}
                                to={`/towns/${city.id}`}
                                className="relative block flex-[0_1_320px] min-w-[280px] no-underline text-inherit rounded-2xl overflow-hidden shadow-[0_2px_8px_rgba(0,0,0,0.08)] bg-white transition-transform transition-shadow duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] hover:scale-105 hover:shadow-[0_8px_32px_rgba(34,60,80,0.18)] focus-visible:outline-2 focus-visible:outline-blue-600 focus-visible:outline-offset-2"
                            >
                                <div className="h-[220px] bg-[#eee]" aria-hidden="true">
                                    <img src={buildPreviewUrl(city)} alt="" loading="lazy"
                                         className="w-full h-full object-cover block"/>
                                </div>
                                <div className="p-3 pt-3 text-center border-t border-[#ccc]">
                                    <h2 className="m-0 text-[1.25rem] font-semibold">{city.city_name}</h2>
                                </div>
                                <div
                                    className="absolute top-2.5 right-2.5 bg-white/80 rounded-full w-9 h-9 grid place-items-center transition-colors duration-200"
                                    title={city.downloaded ? 'Город скачан' : 'Город не скачан'}
                                >
                                    <span
                                        className="material-symbols-outlined text-[24px]"
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
                        <div className="text-center py-6">
                            <button
                                type="button"
                                onClick={handleLoadMore}
                                className="px-8 py-3 text-[1rem] border border-[#bbb] bg-white text-[#222] rounded-md cursor-pointer transition-all duration-200 hover:bg-[#f5f5f5] hover:text-[#222]"
                            >
                                Показать ещё
                            </button>
                        </div>
                    )}

                    {!hasMore && displayedCities.length > 0 && (
                        <div className="text-center text-[#666] py-5 text-[14px]">
                            {search
                                ? pluralizeCity(filteredCities.length)
                                : `Показаны все города (${allCities.length})`}
                        </div>
                    )}

                    {displayedCities.length === 0 && !isLoading && search && (
                        <div className="text-center py-10 px-5 text-[1.1rem]">
                            По запросу "{search}" ничего не найдено.
                        </div>
                    )}
                </>
            )}
        </div>
    );
}