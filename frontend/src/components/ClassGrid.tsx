import React, { useState, useMemo } from 'react';
import { ClassSummaryData } from '../types';
import { Card, CardContent } from './ui/card';
import { Badge } from './ui/badge';
import { Input } from './ui/input';
import {
  GraduationCap,
  Users,
  Search,
  ArrowUpDown,
  ChevronRight,
  BookOpen
} from 'lucide-react';

interface ClassGridProps {
  classes: ClassSummaryData[];
  onSelectClass: (orgId: number, className: string) => void;
  loading?: boolean;
}

type SortOption = 'members_desc' | 'name_asc' | 'id_asc';

export const ClassGrid: React.FC<ClassGridProps> = ({
  classes,
  onSelectClass,
  loading = false,
}) => {
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [sortOption, setSortOption] = useState<SortOption>('members_desc');

  // Filter & sort classes
  const filteredClasses = useMemo(() => {
    let list = [...classes];

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      list = list.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          c.id.toString().includes(q)
      );
    }

    list.sort((a, b) => {
      if (sortOption === 'members_desc') {
        return b.member_count - a.member_count;
      }
      if (sortOption === 'name_asc') {
        return a.name.localeCompare(b.name, 'vi', { numeric: true });
      }
      return a.id - b.id;
    });

    return list;
  }, [classes, searchQuery, sortOption]);

  const totalMembers = useMemo(() => {
    return classes.reduce((sum, c) => sum + c.member_count, 0);
  }, [classes]);

  return (
    <div className="p-3.5 sm:p-5 lg:p-6 max-w-7xl mx-auto space-y-4">
      {/* Header & Controls */}
      <Card className="bg-card border-border">
        <CardContent className="p-4 sm:p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <div className="h-6 w-6 rounded-md bg-brand-primary/10 border border-brand-primary/20 flex items-center justify-center text-brand-primary">
                <GraduationCap className="w-3.5 h-3.5" />
              </div>
              <h1 className="text-lg sm:text-xl font-bold text-text-primary tracking-tight">
                Danh sách lớp học
              </h1>
              <Badge variant="outline" className="text-[10px] font-mono">
                {classes.length} lớp
              </Badge>
            </div>
            <p className="text-xs text-text-secondary">
              Chọn một lớp học để xem danh sách học sinh và phân tích chi tiết năng lực
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            {/* Search Input */}
            <div className="relative w-full sm:w-60">
              <Input
                type="text"
                placeholder="Tìm kiếm lớp học..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 pr-3 h-8 text-xs bg-card"
              />
              <Search className="w-3.5 h-3.5 text-text-tertiary absolute left-2.5 top-2.5 pointer-events-none" />
            </div>

            {/* Sort Selector */}
            <div className="flex items-center gap-1.5 bg-card-subtle px-2 py-1 rounded-md border border-border">
              <ArrowUpDown className="w-3.5 h-3.5 text-text-tertiary flex-shrink-0" />
              <label htmlFor="class-sort-select" className="sr-only">Sắp xếp lớp</label>
              <select
                id="class-sort-select"
                value={sortOption}
                onChange={(e) => setSortOption(e.target.value as SortOption)}
                className="bg-transparent text-xs text-text-primary rounded-md cursor-pointer pr-2 py-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
              >
                <option value="members_desc" className="bg-card text-text-primary">
                  Sĩ số (Nhiều nhất)
                </option>
                <option value="name_asc" className="bg-card text-text-primary">
                  Tên lớp (A → Z)
                </option>
                <option value="id_asc" className="bg-card text-text-primary">
                  Mã lớp (Tăng dần)
                </option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Grid of Classes */}
      {filteredClasses.length === 0 ? (
        <Card className="bg-card border-border">
          <CardContent className="p-8 text-center space-y-2">
            <BookOpen className="w-8 h-8 text-text-tertiary mx-auto opacity-50" />
            <p className="text-sm font-medium text-text-primary">Không tìm thấy lớp học nào</p>
            <p className="text-xs text-text-secondary">
              Vui lòng thử lại với từ khóa tìm kiếm khác.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3.5">
          {filteredClasses.map((cls) => (
            <div
              key={cls.id}
              role="button"
              tabIndex={0}
              onClick={() => onSelectClass(cls.id, cls.name)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onSelectClass(cls.id, cls.name);
                }
              }}
              className="bg-card border border-border hover:border-brand-primary/60 hover:shadow-xs p-4 rounded-lg cursor-pointer transition-all duration-150 flex flex-col justify-between group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <Badge variant="outline" className="text-[10px] font-mono text-text-tertiary">
                    #{cls.id}
                  </Badge>
                  <div className="flex items-center gap-1 text-[11px] text-text-secondary font-medium">
                    <Users className="w-3 h-3 text-brand-primary" />
                    <span>{cls.member_count} HS</span>
                  </div>
                </div>

                <h3 className="text-xs sm:text-sm font-semibold text-text-primary group-hover:text-brand-primary transition-colors line-clamp-2">
                  {cls.name}
                </h3>
              </div>

              <div className="pt-3 mt-3 border-t border-border/50 flex items-center justify-between text-[11px] text-text-tertiary group-hover:text-brand-primary transition-colors">
                <span>Xem học sinh</span>
                <ChevronRight className="w-3.5 h-3.5 transform group-hover:translate-x-0.5 transition-transform" />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
