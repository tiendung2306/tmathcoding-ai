import React from 'react';
import { Search, User, RotateCcw } from 'lucide-react';
import { Input } from '../ui/input';
import { Role } from '../RoleSelect';

interface HeaderProps {
  activeTab: Role;
  onChangeRole: () => void;
  studentId: number;
  studentName?: string;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  onSearchSubmit: () => void;
  studentStep?: 'classes' | 'students' | 'detail';
  onNavigateStudentStep?: (step: 'classes' | 'students' | 'detail') => void;
  virtualClassStep?: 'classes' | 'sessions' | 'live';
  onNavigateVirtualClassStep?: (step: 'classes' | 'sessions' | 'live') => void;
}

const TAB_LABEL: Record<Role, string> = {
  student: 'Học sinh',
  teacher: 'Lớp học ảo',
  admin: 'Quản trị viên',
};

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  onChangeRole,
  studentId,
  studentName,
  searchQuery,
  setSearchQuery,
  onSearchSubmit,
  studentStep = 'classes',
  onNavigateStudentStep,
  virtualClassStep = 'classes',
  onNavigateVirtualClassStep,
}) => {

  return (
    <header className="h-14 border-b border-border bg-card px-3 sm:px-5 grid grid-cols-[auto_minmax(0,1fr)] sm:grid-cols-[minmax(0,1fr)_minmax(0,36rem)_minmax(0,1fr)] items-center gap-2 sm:gap-4 sticky top-0 z-20">
      {/* Left: Brand + Role Context + Switch */}
      <div className="flex items-center gap-2 sm:gap-3 text-xs text-text-secondary min-w-0">
        <div className="flex items-center gap-1.5 shrink-0">
          <img
            src="/tmath-logo.png"
            alt=""
            className="h-6 w-6 rounded-sm object-contain select-none"
            draggable={false}
          />
          <span className="hidden sm:inline font-semibold text-text-primary">tmath OJ</span>
        </div>
        <span className="hidden sm:inline text-border">/</span>
        <div className="hidden sm:flex items-center gap-2 min-w-0">
          {activeTab === 'student' && studentStep !== 'classes' ? (
            <button
              type="button"
              onClick={() => onNavigateStudentStep?.('classes')}
              className="font-medium text-text-primary hover:text-brand-primary hover:underline transition-colors"
            >
              {TAB_LABEL[activeTab]}
            </button>
          ) : activeTab === 'teacher' && virtualClassStep !== 'classes' ? (
            <button
              type="button"
              onClick={() => onNavigateVirtualClassStep?.('classes')}
              className="font-medium text-text-primary hover:text-brand-primary hover:underline transition-colors"
            >
              {TAB_LABEL[activeTab]}
            </button>
          ) : (
            <span className="font-medium text-text-primary truncate">{TAB_LABEL[activeTab]}</span>
          )}
          {activeTab === 'teacher' && virtualClassStep === 'live' && (
            <span className="flex items-center gap-1.5 text-text-secondary truncate">
              <span className="text-border">/</span>
              <button
                type="button"
                onClick={() => onNavigateVirtualClassStep?.('sessions')}
                className="font-medium text-text-primary hover:text-brand-primary hover:underline transition-colors truncate max-w-[120px] sm:max-w-[160px]"
              >
                Phiên học
              </button>
            </span>
          )}
          {activeTab === 'student' && studentStep === 'detail' && (
            <span className="flex items-center gap-1.5 text-text-secondary truncate">
              <span className="text-border">/</span>
              <User className="w-3.5 h-3.5 text-brand-primary shrink-0" />
              <span className="truncate max-w-[120px] sm:max-w-[160px]">
                {studentName || `User ${studentId}`}
              </span>
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={onChangeRole}
          className="flex items-center gap-1 text-[11px] text-text-secondary hover:text-text-primary rounded-md px-1.5 py-1 hover:bg-card-subtle transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary shrink-0"
          aria-label="Đổi vai trò"
        >
          <RotateCcw className="w-3 h-3" />
          <span className="hidden sm:inline">Đổi vai trò</span>
        </button>
      </div>

      {/* Center: Global Search — luôn đứng giữa nhờ cột giữa của grid */}
      <div className="min-w-0">
        <div className="relative w-full">
          <Input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && onSearchSubmit()}
            placeholder="Tìm học sinh..."
            aria-label="Tìm kiếm học sinh toàn hệ thống"
            className="pl-8 pr-12 h-8 text-xs bg-card"
          />
          <Search className="w-3.5 h-3.5 text-text-tertiary absolute left-2.5 top-2.5 pointer-events-none" />
          <kbd className="hidden sm:inline-flex absolute right-2 top-1.5 pointer-events-none h-5 select-none items-center rounded-sm border border-border bg-card-subtle px-1.5 font-mono text-[9px] font-medium text-text-secondary">
            Enter
          </kbd>
        </div>
      </div>

      {/* Cột phải trống (từ sm trở lên): giữ search thẳng giữa */}
      <div aria-hidden="true" className="hidden sm:block" />
    </header>
  );
};
