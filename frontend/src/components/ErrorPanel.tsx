import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface ErrorPanelProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export const ErrorPanel: React.FC<ErrorPanelProps> = ({
  title = 'Không thể tải dữ liệu',
  message,
  onRetry
}) => (
  <div className="bg-red-50 border border-red-200 rounded-lg p-6 flex flex-col items-center justify-center text-center gap-3">
    <AlertTriangle className="w-7 h-7 text-red-600" />
    <div>
      <h3 className="text-sm font-semibold text-red-700">{title}</h3>
      <p className="text-xs text-text-secondary mt-1 max-w-md">{message}</p>
    </div>
    {onRetry && (
      <button
        onClick={onRetry}
        className="flex items-center gap-2 bg-card border border-border hover:border-border-strong hover:bg-card-hover text-text-primary text-xs font-medium px-3.5 py-1.5 rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
      >
        <RefreshCw className="w-3.5 h-3.5" />
        Thử lại
      </button>
    )}
  </div>
);