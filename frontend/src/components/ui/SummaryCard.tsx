import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { Card } from './Card';
import { Badge } from './Badge';
import type { BadgeVariant } from './Badge';

export interface SummaryCardProps {
  title: string;
  icon: LucideIcon;
  value?: string | number | null;
  subtitle?: string;
  badgeText?: string;
  badgeVariant?: BadgeVariant;
  actionText?: string;
  onAction?: () => void;
  className?: string;
}

export const SummaryCard: React.FC<SummaryCardProps> = ({
  title,
  icon: Icon,
  value,
  subtitle = 'Connect data to begin',
  badgeText = 'Awaiting Data',
  badgeVariant = 'neutral',
  actionText,
  onAction,
  className = '',
}) => {
  const displayValue = value ?? 'Not available yet';

  return (
    <Card className={`p-5 transition-all hover:border-slate-300 ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-[#667085] tracking-tight">{title}</span>
        <div className="w-8 h-8 rounded-lg bg-slate-50 border border-slate-200/60 flex items-center justify-center text-slate-500">
          <Icon className="w-4 h-4" />
        </div>
      </div>

      <div className="space-y-1 mb-3">
        <div className="text-xl font-bold text-[#172033] tracking-tight">
          {displayValue}
        </div>
        <div className="text-xs text-[#667085]">{subtitle}</div>
      </div>

      <div className="flex items-center justify-between pt-2 border-t border-[#F1F5F9]">
        <Badge variant={badgeVariant} dot size="sm">
          {badgeText}
        </Badge>
        {actionText && onAction && (
          <button
            onClick={onAction}
            className="text-xs text-blue-600 hover:text-blue-700 font-medium cursor-pointer"
          >
            {actionText}
          </button>
        )}
      </div>
    </Card>
  );
};
