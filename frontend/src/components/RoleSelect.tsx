import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';

export type Role = 'student' | 'teacher' | 'admin';

const ROLE_OPTIONS: { id: Role; label: string }[] = [
  { id: 'student', label: 'Học sinh' },
  { id: 'teacher', label: 'Lớp học ảo' },
  { id: 'admin', label: 'Quản trị viên' },
];

export const RoleSelect: React.FC = () => {
  useEffect(() => { document.title = 'Chọn khu vực làm việc · tmath'; }, []);
  return (
    <div className="min-h-screen bg-app flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="bg-slate-900 p-6 rounded-2xl mx-auto mb-10 w-fit shadow-lg">
          <img
            src="/tmath-logo.png"
            alt="TMATH EDU - Nuôi dưỡng đam mê Toán - Tin"
            className="h-32 w-auto select-none"
            draggable={false}
          />
        </div>

        <h1 className="text-xl font-semibold text-center mb-5">Chọn khu vực làm việc</h1>
        <nav className="grid grid-cols-1 sm:grid-cols-3 gap-2.5" aria-label="Khu vực làm việc">
          {ROLE_OPTIONS.map((option) => (
            <Link
              key={option.id}
              to={option.id === 'admin' ? '/admin' : `/${option.id}/classes`}
              className="min-h-11 flex items-center justify-center px-2 bg-card border border-border-control rounded-md text-sm font-medium text-text-primary transition-colors hover:border-text-secondary hover:bg-card-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
            >
              {option.label}
            </Link>
          ))}
        </nav>
      </div>
    </div>
  );
};
