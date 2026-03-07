'use client';

import React from 'react';
import { cn } from '@/lib/utils';

export type FormFieldVariant = 'text' | 'select' | 'textarea';

export interface SelectOption {
  value: string;
  label: string;
}

export interface FormFieldProps {
  /** Field label */
  label: string;
  /** Input name attribute */
  name: string;
  /** Field variant type */
  variant?: FormFieldVariant;
  /** Current value */
  value?: string;
  /** Change handler */
  onChange?: (value: string) => void;
  /** Placeholder text */
  placeholder?: string;
  /** Whether field is required */
  required?: boolean;
  /** Helper text displayed below input */
  helperText?: string;
  /** Error message */
  error?: string;
  /** Additional CSS classes for container */
  className?: string;
  /** Additional CSS classes for input */
  inputClassName?: string;
  /** Disabled state */
  disabled?: boolean;
  /** Options for select variant */
  options?: SelectOption[];
  /** Input type (for text variant) */
  type?: 'text' | 'email' | 'number' | 'password';
  /** Number of rows (for textarea variant) */
  rows?: number;
}

/**
 * FormField - 统一输入框组件
 * 
 * Supports text, select, and textarea variants with consistent styling.
 * Based on XJCG form input patterns.
 */
export function FormField({
  label,
  name,
  variant = 'text',
  value,
  onChange,
  placeholder,
  required = false,
  helperText,
  error,
  className,
  inputClassName,
  disabled = false,
  options = [],
  type = 'text',
  rows = 4,
}: FormFieldProps) {
  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    onChange?.(e.target.value);
  };

  const inputWrapperClass = 'space-y-1.5';
  const labelClass = 'block text-sm font-semibold text-[var(--foreground)]';
  const requiredMarkerClass = 'ml-1 text-[var(--error)]';
  const helperClass = 'text-xs leading-5 text-[var(--text-muted)]';
  const errorClass = 'text-xs leading-5 text-[var(--error)]';

  const baseInputClass = cn(
    'input-field w-full rounded-xl px-3.5 py-2.5 text-sm leading-5 shadow-none',
    error && 'border-[var(--error)] focus:border-[var(--error)] focus:ring-[var(--error)]/20',
    disabled && 'cursor-not-allowed opacity-60',
    inputClassName
  );

  return (
    <div className={cn(inputWrapperClass, className)}>
      <label htmlFor={name} className={labelClass}>
        {label}
        {required && <span className={requiredMarkerClass}>*</span>}
      </label>

      {variant === 'text' && (
        <input
          id={name}
          name={name}
          type={type}
          value={value}
          onChange={handleChange}
          placeholder={placeholder}
          disabled={disabled}
          className={baseInputClass}
        />
      )}

      {variant === 'textarea' && (
        <textarea
          id={name}
          name={name}
          value={value}
          onChange={handleChange}
          placeholder={placeholder}
          disabled={disabled}
          rows={rows}
          className={cn(baseInputClass, 'resize-y')}
        />
      )}

      {variant === 'select' && (
        <select
          id={name}
          name={name}
          value={value}
          onChange={handleChange}
          disabled={disabled}
          className={cn(baseInputClass, 'cursor-pointer appearance-none bg-[right_0.5rem_center] bg-no-repeat pr-10')}
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%236b7280'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'%3E%3C/path%3E%3C/svg%3E")`,
            backgroundSize: '1.5rem',
          }}
        >
          {placeholder && (
            <option value="" disabled>
              {placeholder}
            </option>
          )}
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      )}

      {helperText && !error && <p className={helperClass}>{helperText}</p>}
      {error && <p className={errorClass}>{error}</p>}
    </div>
  );
}

export default FormField;
