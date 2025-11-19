import React from 'react'
import {Link} from 'react-router-dom'

export const Toolbar: React.FC = () => (
    <div
        className="fixed top-0 left-0 right-0 py-2 bg-[rgba(248,248,248,0.5)] backdrop-blur-md border-b border-[rgba(200,199,196,0.3)] flex items-center justify-between px-4 md:px-8 z-[1000] shadow-md h-[56px] text-black">
        <div className="flex-1 flex items-center">
            <Link
                to="/"
                className="font-bold text-[20px] text-black no-underline transition-colors duration-500 hover:text-black"
            >
                Urban Topology
            </Link>
        </div>
        <div className="flex-1 flex justify-end items-center">
            <a
                href="https://github.com/citec-spbu/Urban-Topology"
                target="_blank"
                rel="noopener noreferrer"
                className="text-black text-[20px] transition-colors duration-500 font-medium flex items-center gap-1 hover:text-[#6e40c9]"
            >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path
                        d="M12 0C5.37 0 0 5.373 0 12c0 5.303 3.438 9.8 8.205 11.387.6.113.82-.258.82-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.085 1.84 1.237 1.84 1.237 1.07 1.834 2.809 1.304 3.495.997.108-.775.418-1.305.762-1.606-2.665-.305-5.466-1.334-5.466-5.931 0-1.31.469-2.381 1.236-3.221-.124-.303-.535-1.523.117-3.176 0 0 1.008-.322 3.301 1.23a11.52 11.52 0 0 1 3.003-.404c1.018.005 2.045.138 3.003.404 2.291-1.553 3.297-1.23 3.297-1.23.653 1.653.242 2.873.119 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.804 5.624-5.475 5.921.43.372.823 1.102.823 2.222v3.293c0 .322.218.694.825.576C20.565 21.796 24 17.299 24 12c0-6.627-5.373-12-12-12z"/>
                </svg>
                GitHub
            </a>
        </div>
    </div>
);