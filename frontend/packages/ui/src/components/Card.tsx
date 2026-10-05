import React from "react";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

export const Card: React.FC<CardProps> = ({ children, className = "", ...props }) => {
  return (
    <div
      className={`bg-white border border-slate-200 rounded-xl shadow-xs overflow-hidden ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};

export const CardHeader: React.FC<CardProps> = ({ children, className = "", ...props }) => {
  return (
    <div className={`px-6 py-4 border-b border-slate-100 ${className}`} {...props}>
      {children}
    </div>
  );
};

export const CardTitle: React.FC<React.HTMLAttributes<HTMLHeadingElement>> = ({
  children,
  className = "",
  ...props
}) => {
  return (
    <h3 className={`text-base font-semibold text-slate-900 ${className}`} {...props}>
      {children}
    </h3>
  );
};

export const CardDescription: React.FC<React.HTMLAttributes<HTMLParagraphElement>> = ({
  children,
  className = "",
  ...props
}) => {
  return (
    <p className={`text-sm text-slate-500 mt-0.5 ${className}`} {...props}>
      {children}
    </p>
  );
};

export const CardContent: React.FC<CardProps> = ({ children, className = "", ...props }) => {
  return (
    <div className={`p-6 ${className}`} {...props}>
      {children}
    </div>
  );
};

export const CardFooter: React.FC<CardProps> = ({ children, className = "", ...props }) => {
  return (
    <div
      className={`px-6 py-4 bg-slate-50 border-t border-slate-100 flex items-center justify-between ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};
