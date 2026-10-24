import React from 'react';
import { Info, AlertTriangle, CheckCircle, AlertCircle } from 'lucide-react';

export type AlertVariant = 'info' | 'warning' | 'success' | 'error';

export interface AlertProps {
  variant?: AlertVariant;
  title?: string;
  children: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

const variantStyles: Record<AlertVariant, { container: string; icon: React.ReactNode; title: string }> = {
  info: {
    container: 'bg-blue-50/70 border-blue-200 text-blue-900',
    icon: <Info className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />,
    title: 'text-blue-900 font-semibold',
  },
  warning: {
    container: 'bg-amber-50/70 border-amber-200 text-amber-900',
    icon: <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />,
    title: 'text-amber-900 font-semibold',
  },
  success: {
    container: 'bg-emerald-50/70 border-emerald-200 text-emerald-900',
    icon: <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />,
    title: 'text-emerald-900 font-semibold',
  },
  error: {
    container: 'bg-rose-50/70 border-rose-200 text-rose-900',
    icon: <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />,
    title: 'text-rose-900 font-semibold',
  },
};

export const Alert: React.FC<AlertProps> = ({
  variant = 'info',
  title,
  children,
  action,
  className = '',
}) => {
  const styles = variantStyles[variant];

  return (
    <div className={`p-4 rounded-xl border flex items-start gap-3 text-xs leading-relaxed ${styles.container} ${className}`}>
      {styles.icon}
      <div className="flex-1 min-w-0">
        {title && <h5 className={`text-xs mb-0.5 ${styles.title}`}>{title}</h5>}
        <div className="text-slate-700">{children}</div>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
};
