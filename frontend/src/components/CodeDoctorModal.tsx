import React from 'react';
import { CodeDoctorResponseData } from '../types';
import { Stethoscope, HelpCircle, Lightbulb, AlertCircle } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from './ui/dialog';
import { Badge } from './ui/badge';
import { Button } from './ui/button';

interface CodeDoctorModalProps {
  data: CodeDoctorResponseData | null;
  onClose: () => void;
}

export const CodeDoctorModal: React.FC<CodeDoctorModalProps> = ({ data, onClose }) => {
  return (
    <Dialog open={!!data} onOpenChange={(open) => !open && onClose()}>
      {data && (
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-md bg-red-100 border border-red-200 flex items-center justify-center text-red-600 flex-shrink-0">
                <Stethoscope className="w-5 h-5" />
              </div>
              <div className="space-y-0.5">
                <DialogTitle className="text-base font-semibold flex items-center gap-2">
                  Chẩn đoán bài nộp
                  <Badge variant="wa" className="text-[10px]">
                    {data.diagnosis.error_category}
                  </Badge>
                </DialogTitle>
                <DialogDescription className="text-xs">
                  Phân tích nguyên nhân và gợi ý định hướng cho bài toán:{' '}
                  <span className="text-text-primary font-medium">{data.problem_name}</span>
                </DialogDescription>
              </div>
            </div>
          </DialogHeader>

          <div className="space-y-3.5 py-1 text-xs">
            {/* Error Summary */}
            <div className="rounded-md border border-red-200 bg-red-50 p-3.5 space-y-1">
              <div className="flex items-center gap-2 text-red-700 font-medium">
                <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
                <span>Bản chất sự cố</span>
              </div>
              <p className="text-text-secondary leading-relaxed pl-5">
                {data.diagnosis.summary}
              </p>
            </div>

            {/* Guiding Question Box */}
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3.5 space-y-1.5">
              <div className="flex items-center gap-2 text-amber-700 font-medium">
                <HelpCircle className="w-3.5 h-3.5 flex-shrink-0" />
                <span>Câu hỏi gợi mở tư duy</span>
              </div>
              <p className="text-amber-900 leading-relaxed pl-5">
                "{data.diagnosis.guiding_question}"
              </p>
            </div>

            {/* Actionable Hint */}
            <div className="rounded-md border border-blue-200 bg-blue-50 p-3.5 space-y-1">
              <div className="flex items-center gap-2 text-blue-700 font-medium">
                <Lightbulb className="w-3.5 h-3.5 flex-shrink-0" />
                <span>Hướng dẫn xử lý</span>
              </div>
              <p className="text-text-primary leading-relaxed pl-5">
                {data.diagnosis.actionable_hint}
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={onClose}
              className="text-xs"
            >
              Đóng
            </Button>
          </DialogFooter>
        </DialogContent>
      )}
    </Dialog>
  );
};
