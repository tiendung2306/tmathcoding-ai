import React from "react";
import { Search, ChevronRight, User, Menu } from "lucide-react";
import { Input } from "../ui/input";
import { Badge } from "../ui/badge";

interface HeaderProps {
  activeTab: "student" | "teacher";
  studentId: number;
  studentName?: string;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  onSearchSubmit: () => void;
  onToggleMobileMenu?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  studentId,
  studentName,
  searchQuery,
  setSearchQuery,
  onSearchSubmit,
  onToggleMobileMenu,
}) => {
  return (
    <header className="h-14 border-b border-border bg-card px-3.5 sm:px-6 flex items-center justify-between sticky top-0 z-20 gap-3">
      {/* Mobile Menu Button + Breadcrumbs */}
      <div className="flex items-center gap-2 text-xs text-text-secondary min-w-0">
        {onToggleMobileMenu && (
          <button
            type="button"
            onClick={onToggleMobileMenu}
            className="md:hidden h-9 w-9 grid place-items-center -ml-1.5 text-text-secondary hover:text-text-primary rounded-md hover:bg-card-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
            aria-label="Mở menu"
          >
            <Menu className="w-4 h-4" />
          </button>
        )}
        <span className="font-semibold text-text-primary hidden sm:inline">tmath OJ</span>
        <ChevronRight className="w-3.5 h-3.5 text-text-tertiary hidden sm:inline" />
        <span className="text-text-secondary truncate">
          {activeTab === "student" ? "Học sinh" : "Giáo viên"}
        </span>
        <ChevronRight className="w-3.5 h-3.5 text-text-tertiary" />
        <span className="font-medium text-text-primary flex items-center gap-1.5 truncate">
          {activeTab === "student" ? (
            <>
              <User className="w-3.5 h-3.5 text-brand-primary shrink-0" />
              <span className="truncate">{studentName || `User ${studentId}`}</span>
              <Badge variant="secondary" className="text-[10px] py-0 px-1 font-mono shrink-0">
                #{studentId}
              </Badge>
            </>
          ) : (
            <span>Danh sách lớp học</span>
          )}
        </span>
      </div>

      {/* Quick Search */}
      <div className="relative w-44 sm:w-64 md:w-72 shrink-0">
        <Input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onSearchSubmit()}
          placeholder="Tìm học sinh..."
          aria-label="Tìm kiếm học sinh"
          className="pl-8 pr-12 h-8 text-xs bg-card"
        />
        <Search className="w-3.5 h-3.5 text-text-tertiary absolute left-2.5 top-2.5 pointer-events-none" />
        <kbd className="hidden sm:inline-flex absolute right-2 top-1.5 pointer-events-none h-5 select-none items-center rounded-sm border border-border bg-card-subtle px-1.5 font-mono text-[9px] font-medium text-text-secondary">
          Enter
        </kbd>
      </div>
    </header>
  );
};
