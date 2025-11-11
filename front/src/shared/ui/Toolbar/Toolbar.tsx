import React from 'react'
import { Link } from 'react-router-dom'
import './Toolbar.css'

export const Toolbar: React.FC = () => (
    <div className="toolbar">
        <h1 className="logo">
            <Link to="/">Urban Topology</Link>
        </h1>
    </div>
);
