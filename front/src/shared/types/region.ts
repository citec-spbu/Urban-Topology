export interface Region {
    id: number;
    admin_level: number;
    name: string;
    type: 'Polygon';
    regions: [number, number][][];
}
