import React from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, Home } from 'lucide-react';
import { Button } from '../components/ui/Button';

export const NotFoundPage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center p-8">
      <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center text-slate-500 mb-4">
        <AlertCircle className="w-6 h-6" />
      </div>
      <h2 className="text-xl font-bold text-[#172033] mb-2">Page Not Found</h2>
      <p className="text-xs sm:text-sm text-[#667085] max-w-sm mb-6">
        The requested screen does not exist in the StockWise application shell.
      </p>
      <Button
        variant="primary"
        leftIcon={<Home className="w-4 h-4" />}
        onClick={() => navigate('/')}
      >
        Return to Overview
      </Button>
    </div>
  );
};
