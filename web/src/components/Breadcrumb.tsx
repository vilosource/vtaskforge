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
    <nav className="flex items-center gap-2 text-sm text-on-surface-variant pt-3" aria-label="Breadcrumb">
      {segments.map((segment, index) => (
        <React.Fragment key={index}>
          {index > 0 && (
            <span className="material-symbols-outlined text-sm">chevron_right</span>
          )}
          {segment.to ? (
            <Link to={segment.to} className="font-medium hover:text-primary transition-colors">
              {segment.label}
            </Link>
          ) : (
            <span className="font-bold text-on-surface">{segment.label}</span>
          )}
        </React.Fragment>
      ))}
    </nav>
  );
}
