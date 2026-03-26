import React from 'react';
import { Link } from 'react-router-dom';

interface BreadcrumbSegment {
  label: string;
  to?: string;
}

interface BreadcrumbProps {
  segments: BreadcrumbSegment[];
}

export function Breadcrumb({ segments }: BreadcrumbProps) {
  return (
    <nav className="breadcrumb" aria-label="Breadcrumb">
      {segments.map((segment, index) => (
        <React.Fragment key={index}>
          {index > 0 && <span className="breadcrumb-separator">/</span>}
          {segment.to ? (
            <Link to={segment.to} className="breadcrumb-link">
              {segment.label}
            </Link>
          ) : (
            <span className="breadcrumb-current">{segment.label}</span>
          )}
        </React.Fragment>
      ))}
    </nav>
  );
}
