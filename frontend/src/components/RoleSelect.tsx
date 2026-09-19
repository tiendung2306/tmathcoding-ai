import React from 'react';

export type Role = 'student' | 'teacher' | 'admin';

interface RoleSelectProps {
  onSelectRole: (role: Role) => void;
}

const ROLE_OPTIONS: { id: Role; label: string }[] = [
  { id: 'student', label: 'Học sinh' },
  { id: 'teacher', label: 'Giáo viên' },
  { id: 'admin', label: 'Quản trị viên' },
];

export const RoleSelect: React.FC<RoleSelectProps> = ({ onSelectRole }) => {
  return (
    <div className="min-h-screen bg-app flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <img
          src="/tmath-logo.png"
          alt="TMATH EDU - Nuôi dưỡng đam mê Toán - Tin"
          className="h-44 w-auto mx-auto mb-10 select-none"
          draggable={false}
        />

        <div className="grid grid-cols-3 gap-2.5" role="group" aria-label="Chọn vai trò">
          {ROLE_OPTIONS.map((option) => (
            <button
              key={option.id}
              type="button"
              onClick={() => onSelectRole(option.id)}
              className="h-10 px-2 bg-card border border-border rounded-md text-sm font-medium text-text-primary transition-colors hover:border-border-strong hover:bg-card-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};