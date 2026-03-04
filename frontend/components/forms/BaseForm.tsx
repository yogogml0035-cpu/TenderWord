'use client';

import React, { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';

export interface FormField {
  name: string;
  label: string;
  type: 'text' | 'textarea' | 'select' | 'file' | 'custom';
  required?: boolean;
  placeholder?: string;
  options?: { value: string; label: string }[];
  component?: React.ReactNode;
  validation?: (value: unknown) => string | null;
}

export interface BaseFormProps {
  title?: string;
  description?: string;
  fields: FormField[];
  onSubmit: (data: Record<string, unknown>) => Promise<void> | void;
  submitText?: string;
  loadingText?: string;
  className?: string;
  children?: React.ReactNode;
  initialValues?: Record<string, unknown>;
  validate?: (data: Record<string, unknown>) => string | null;
}

export function BaseForm({
  title,
  description,
  fields,
  onSubmit,
  submitText = '提交',
  loadingText = '提交中...',
  className,
  children,
  initialValues = {},
  validate,
}: BaseFormProps) {
  const [formData, setFormData] = useState<Record<string, unknown>>(initialValues);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);

  const updateField = useCallback((name: string, value: unknown) => {
    setFormData((prev) => ({ ...prev, [name]: value }));
    // Clear error when field is updated
    setErrors((prev) => {
      const newErrors = { ...prev };
      delete newErrors[name];
      return newErrors;
    });
    setGlobalError(null);
  }, []);

  const validateForm = useCallback((): boolean => {
    const newErrors: Record<string, string> = {};

    // Validate each field
    fields.forEach((field) => {
      if (field.required) {
        const value = formData[field.name];
        if (value === undefined || value === null || value === '') {
          newErrors[field.name] = `${field.label}不能为空`;
        }
      }
      if (field.validation && formData[field.name] !== undefined) {
        const error = field.validation(formData[field.name]);
        if (error) {
          newErrors[field.name] = error;
        }
      }
    });

    // Global validation
    if (validate) {
      const globalValidationError = validate(formData);
      if (globalValidationError) {
        setGlobalError(globalValidationError);
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0 && !globalError;
  }, [fields, formData, validate, globalError]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();

      if (!validateForm()) {
        return;
      }

      setIsSubmitting(true);
      setGlobalError(null);

      try {
        await onSubmit(formData);
      } catch (error) {
        setGlobalError(error instanceof Error ? error.message : '提交失败，请重试');
      } finally {
        setIsSubmitting(false);
      }
    },
    [validateForm, onSubmit, formData]
  );

  const renderField = (field: FormField) => {
    const value = formData[field.name];
    const error = errors[field.name];

    const baseInputClasses = cn(
      'input-field w-full',
      error && 'border-[var(--error)] focus:ring-[var(--error)]'
    );

    switch (field.type) {
      case 'text':
        return (
          <input
            type="text"
            id={field.name}
            name={field.name}
            value={(value as string) || ''}
            onChange={(e) => updateField(field.name, e.target.value)}
            placeholder={field.placeholder}
            className={baseInputClasses}
            disabled={isSubmitting}
          />
        );

      case 'textarea':
        return (
          <textarea
            id={field.name}
            name={field.name}
            value={(value as string) || ''}
            onChange={(e) => updateField(field.name, e.target.value)}
            placeholder={field.placeholder}
            rows={4}
            className={cn(baseInputClasses, 'min-h-[100px] resize-y')}
            disabled={isSubmitting}
          />
        );

      case 'select':
        return (
          <select
            id={field.name}
            name={field.name}
            value={(value as string) || ''}
            onChange={(e) => updateField(field.name, e.target.value)}
            className={baseInputClasses}
            disabled={isSubmitting}
          >
            <option value="">请选择</option>
            {field.options?.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        );

      case 'custom':
        return field.component;

      default:
        return null;
    }
  };

  return (
    <form onSubmit={handleSubmit} className={cn('form-section', className)}>
      {title && (
        <div className="mb-6">
          <h2 className="text-xl font-semibold text-[var(--foreground)]">{title}</h2>
          {description && <p className="mt-1 text-sm text-[var(--text-muted)]">{description}</p>}
        </div>
      )}

      {globalError && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-[var(--error)]">{globalError}</p>
        </div>
      )}

      <div className="space-y-5">
        {fields.map((field) => (
          <div key={field.name} className="space-y-2">
            <label
              htmlFor={field.name}
              className="block text-sm font-medium text-[var(--foreground)]"
            >
              {field.label}
              {field.required && <span className="ml-1 text-[var(--error)]">*</span>}
            </label>
            {renderField(field)}
            {errors[field.name] && (
              <p className="text-sm text-[var(--error)]">{errors[field.name]}</p>
            )}
          </div>
        ))}
      </div>

      {children}

      <div className="pt-6">
        <button type="submit" disabled={isSubmitting} className="btn-primary w-full">
          {isSubmitting ? (
            <>
              <LoadingSpinner className="mr-2" />
              {loadingText}
            </>
          ) : (
            submitText
          )}
        </button>
      </div>
    </form>
  );
}

function LoadingSpinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn('h-4 w-4 animate-spin', className)}
      width={16}
      height={16}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}

export default BaseForm;
