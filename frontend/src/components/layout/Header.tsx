import React from 'react';
import { Search, ChevronRight, User, Menu, BookOpen, Users } from 'lucide-react';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { ClassSummaryData, ClassStudentItemData } from '../../types';

interface HeaderProps {
  activeTab: 'student' | 'teacher' | 'admin';
  classes?: ClassSummaryData[];
  selectedOrgId?: number;
  onSelectOrgId?: (orgId: number) => void;
  classStudents?: ClassStudentItemData[];
  studentId: number;
  studentName?: string;
  onSelectStudent?: (studentId: number, studentName: string) => void;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  onSearchSubmit: () => void;
  onToggleMobileMenu?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  classes = [],
  selectedOrgId,
  onSelectOrgId,
  classStudents = [],
  studentId,
  studentName,
  onSelectStudent,
  searchQuery,
  setSearchQuery,
  onSearchSubmit,
  onToggleMobileMenu,
}) => {
  const handleStudentDropdownChange = (newUserId: number) => {
    const found = classStudents.find((s) => s.user_id === newUserId);
    if (found && onSelectStudent) {
      onSelectStudent(found.user_id, found.name);
    }
  };

  return (
    <header className="h-14 border-b border-border bg-card px-3 sm:px-5 flex items-center justify-between sticky top-0 z-20 gap-2 sm:gap-4">
      {/* Left: Mobile Menu Trigger + Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-text-secondary min-w-0">
        {onToggleMobileMenu && (
          <button
            type="button"
            onClick={onToggleMobileMenu}
            className="md:hidden h-8 w-8 grid place-items-center -ml-1 text-text-secondary hover:text-text-primary rounded-md hover:bg-card-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
            aria-label="Mở menu"
          >
            <Menu className="w-4 h-4" />
          </button>
        )}
        <span className="font-semibold text-text-primary hidden md:inline">tmath OJ</span>
        <ChevronRight className="w-3.5 h-3.5 text-text-tertiary hidden md:inline" />
        <span className="text-text-secondary truncate">
          {activeTab === 'student' ? 'Học sinh' : activeTab === 'teacher' ? 'Giáo viên' : 'Quản trị'}
        </span>
        <ChevronRight className="w-3.5 h-3.5 text-text-tertiary" />
        <span className="font-medium text-text-primary flex items-center gap-1.5 truncate">
          {activeTab === 'student' ? (
            <>
              <User className="w-3.5 h-3.5 text-brand-primary shrink-0" />
              <span className="truncate max-w-[120px] sm:max-w-[160px]">{studentName || `User ${studentId}`}</span>
              <Badge variant="secondary" className="text-[10px] py-0 px-1 font-mono shrink-0">
                #{studentId}
              </Badge>
            </>
          ) : activeTab === 'teacher' ? (
            <span>Quản lý lớp học</span>
          ) : (
            <span>Gắn nhãn tự động</span>
          )}
        </span>
      </div>

      {/* Center: Dual Context Selector (Lớp học + Học sinh) */}
      {activeTab !== 'admin' && classes.length > 0 && (
        <div className="hidden lg:flex items-center gap-2 bg-card-subtle/80 border border-border rounded-md px-2 py-1">
          {/* Chọn Lớp */}
          <div className="flex items-center gap-1.5 min-w-0">
            <BookOpen className="w-3.5 h-3.5 text-text-tertiary shrink-0" />
            <label htmlFor="header-class-select" className="sr-only">Chọn lớp học</label>
            <select
              id="header-class-select"
              value={selectedOrgId || ''}
              onChange={(e) => onSelectOrgId?.(Number(e.target.value))}
              aria-label="Chọn lớp học"
              className="bg-transparent text-xs text-text-primary rounded cursor-pointer max-w-[180px] truncate focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-primary py-0.5"
            >
              {classes.map((c) => (
                <option key={c.id} value={c.id} className="bg-card text-text-primary">
                  {c.name} ({c.member_count} HS)
                </option>
              ))}
            </select>
          </div>

          <span className="text-border text-sm">/</span>

          {/* Chọn Học sinh trong lớp */}
          <div className="flex items-center gap-1.5 min-w-0">
            <Users className="w-3.5 h-3.5 text-text-tertiary shrink-0" />
            <label htmlFor="header-student-select" className="sr-only">Chọn học sinh trong lớp</label>
            <select
              id="header-student-select"
              value={studentId}
              onChange={(e) => handleStudentDropdownChange(Number(e.target.value))}
              aria-label="Chọn học sinh trong lớp"
              className="bg-transparent text-xs text-text-primary rounded cursor-pointer max-w-[180px] truncate focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-primary py-0.5"
            >
              {classStudents.length === 0 ? (
                <option value={studentId} className="bg-card text-text-primary">
                  {studentName || `User #${studentId}`}
                </option>
              ) : (
                classStudents.map((s) => (
                  <option key={s.user_id} value={s.user_id} className="bg-card text-text-primary">
                    {s.name} (#{s.user_id})
                  </option>
                ))
              )}
            </select>
          </div>
        </div>
      )}

      {/* Right: Global Search Input */}
      <div className="relative w-36 sm:w-56 md:w-64 shrink-0">
        <Input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onSearchSubmit()}
          placeholder="Tìm bất kỳ học sinh..."
          aria-label="Tìm kiếm học sinh toàn hệ thống"
          className="pl-8 pr-10 sm:pr-12 h-8 text-xs bg-card"
        />
        <Search className="w-3.5 h-3.5 text-text-tertiary absolute left-2.5 top-2.5 pointer-events-none" />
        <kbd className="hidden sm:inline-flex absolute right-2 top-1.5 pointer-events-none h-5 select-none items-center rounded-sm border border-border bg-card-subtle px-1.5 font-mono text-[9px] font-medium text-text-secondary">
          Enter
        </kbd>
      </div>
    </header>
  );
};
