import React from 'react';
import { Cpu, User, Users, Search } from 'lucide-react';

interface NavbarProps {
  activeTab: 'student' | 'teacher';
  setActiveTab: (tab: 'student' | 'teacher') => void;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  onSearchSubmit: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  searchQuery,
  setSearchQuery,
  onSearchSubmit
}) => {
  return (
    <nav className="border-b border-dark-border bg-dark-card/80 backdrop-blur-md sticky top-0 z-40 px-6 py-3.5 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="bg-gradient-to-tr from-brand-blue to-brand-purple p-2 rounded-xl text-white shadow-lg shadow-brand-blue/20">
          <Cpu className="w-6 h-6" />
        </div>
        <div>
          <h1 className="font-bold text-lg leading-none bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
            tmath AI Diagnostic
          </h1>
          <span className="text-xs text-slate-400 font-medium">Production OJ Intelligence</span>
        </div>
      </div>

      {/* Mode Switcher */}
      <div className="flex items-center gap-1 bg-dark-bg p-1 rounded-xl border border-dark-border">
        <button
          onClick={() => setActiveTab('student')}
          className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${
            activeTab === 'student'
              ? 'bg-brand-blue text-white shadow-md shadow-brand-blue/25'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <User className="w-4 h-4" />
          Học sinh (Skill Tree)
        </button>
        <button
          onClick={() => setActiveTab('teacher')}
          className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${
            activeTab === 'teacher'
              ? 'bg-brand-blue text-white shadow-md shadow-brand-blue/25'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Users className="w-4 h-4" />
          Giáo viên (Heatmap)
        </button>
      </div>

      {/* Global Student Search Bar */}
      <div className="relative w-72">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onSearchSubmit()}
          placeholder="Tìm học sinh theo tên/username..."
          className="w-full bg-dark-bg border border-dark-border rounded-xl pl-9 pr-4 py-1.5 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-brand-blue transition-colors"
        />
        <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
      </div>
    </nav>
  );
};
