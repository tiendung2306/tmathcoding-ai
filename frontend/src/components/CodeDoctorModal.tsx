import React from 'react';
import { CodeDoctorResponseData } from '../types';
import { Stethoscope, X, HelpCircle, Lightbulb, AlertCircle } from 'lucide-react';

interface CodeDoctorModalProps {
  data: CodeDoctorResponseData | null;
  onClose: () => void;
}

export const CodeDoctorModal: React.FC<CodeDoctorModalProps> = ({ data, onClose }) => {
  if (!data) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-dark-card border border-dark-border rounded-2xl w-full max-w-xl p-6 shadow-2xl relative animate-modal-in">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 text-slate-400 hover:text-slate-200 bg-dark-bg p-1.5 rounded-lg border border-dark-border"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="bg-rose-500/10 border border-rose-500/20 p-2.5 rounded-xl text-rose-400">
            <Stethoscope className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-100">AI Code Doctor Diagnosing</h2>
            <p className="text-xs text-slate-400">Chẩn đoán Socratic cho Bài toán: <span className="text-brand-blue font-medium">{data.problem_name}</span></p>
          </div>
        </div>

        <div className="space-y-4 text-sm">
          {/* Error Summary */}
          <div className="bg-rose-950/20 border border-rose-500/30 rounded-xl p-4">
            <div className="flex items-center gap-2 text-rose-400 font-semibold mb-1">
              <AlertCircle className="w-4 h-4" />
              Sự cố: {data.diagnosis.error_category}
            </div>
            <p className="text-slate-300 text-xs leading-relaxed">{data.diagnosis.summary}</p>
          </div>

          {/* Guiding Socratic Question */}
          <div className="bg-amber-950/20 border border-amber-500/30 rounded-xl p-4">
            <div className="flex items-center gap-2 text-amber-400 font-semibold mb-1">
              <HelpCircle className="w-4 h-4" />
              Câu hỏi gợi mở cho bạn (Socratic Question):
            </div>
            <p className="text-slate-200 italic text-xs leading-relaxed">"{data.diagnosis.guiding_question}"</p>
          </div>

          {/* Actionable Hint */}
          <div className="bg-brand-blue/10 border border-brand-blue/30 rounded-xl p-4">
            <div className="flex items-center gap-2 text-brand-blue font-semibold mb-1">
              <Lightbulb className="w-4 h-4" />
              Gợi ý bước tiếp theo:
            </div>
            <p className="text-slate-300 text-xs leading-relaxed">{data.diagnosis.actionable_hint}</p>
          </div>
        </div>

        <div className="mt-6 flex justify-end">
          <button
            onClick={onClose}
            className="bg-brand-blue hover:bg-blue-600 text-white font-medium px-5 py-2 rounded-xl text-sm transition-colors shadow-lg shadow-brand-blue/20"
          >
            Đã hiểu, tôi sẽ tự thử sửa code!
          </button>
        </div>
      </div>
    </div>
  );
};
