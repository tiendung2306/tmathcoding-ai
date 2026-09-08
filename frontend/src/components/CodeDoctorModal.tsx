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

          <div className="py-2 text-xs">
            <div className="rounded-md border border-border bg-card-subtle/70 p-4">
              <p className="text-xs sm:text-[13px] text-text-primary leading-relaxed whitespace-pre-wrap font-sans">
                {data.diagnosis.advice || data.diagnosis.summary}
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
