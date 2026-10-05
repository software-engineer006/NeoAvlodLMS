import React from "react";
import { Spinner } from "./Spinner";

export interface LoadingStateProps {
  message?: string;
  className?: string;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = "Yuklanmoqda...",
  className = "",
}) => {
  return (
    <div className={`flex flex-col items-center justify-center py-12 px-4 text-center ${className}`}>
      <Spinner size="lg" className="text-blue-600 mb-3" />
      <p className="text-sm font-medium text-slate-600">{message}</p>
    </div>
  );
};
