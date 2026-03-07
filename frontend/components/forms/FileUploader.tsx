'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { cn, formatFileSize } from '@/lib/utils';
import { Upload, X, AlertCircle, CheckCircle2 } from 'lucide-react';
import { uploadFile, ApiError } from '@/lib/api';
import type { FileType } from '@/types/api';

export interface UploadedFile {
  id: string;
  file?: File;
  file_path: string;
  file_name: string;
  original_name: string;
  size: number;
  upload_time: string;
  file_type?: string;
}

export interface FileUploaderProps {
  onUpload?: (files: UploadedFile[]) => void;
  onFilesChange?: (files: UploadedFile[]) => void;
  onFileSelect?: (files: File[]) => void;
  initialFiles?: UploadedFile[];
  multiple?: boolean;
  accept?: string;
  maxFiles?: number;
  maxSize?: number; // in bytes
  label?: string;
  description?: string;
  disabled?: boolean;
  className?: string;
  autoUpload?: boolean;
  fileType?: FileType;
}

export function FileUploader({
  onUpload,
  onFilesChange,
  onFileSelect,
  initialFiles,
  multiple = false,
  accept = '.doc,.docx',
  maxFiles = 10,
  maxSize = 50 * 1024 * 1024, // 50MB
  label = '上传文件',
  description = '支持 .doc, .docx 格式',
  disabled = false,
  className,
  autoUpload = false,
  fileType,
}: FileUploaderProps) {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const shouldNotifyFilesChangeRef = useRef(false);

  useEffect(() => {
    if (!initialFiles) {
      return;
    }
    setFiles(initialFiles);
  }, [initialFiles]);

  useEffect(() => {
    if (!shouldNotifyFilesChangeRef.current) {
      return;
    }

    shouldNotifyFilesChangeRef.current = false;
    onFilesChange?.(files);
  }, [files, onFilesChange]);

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (disabled) {
        return;
      }
      setIsDragging(true);
    },
    [disabled]
  );

  const handleDragLeave = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
    },
    []
  );

  const validateFile = useCallback(
    (file: File): string | null => {
      if (maxSize && file.size > maxSize) {
        return `文件大小超过限制 (最大 ${formatFileSize(maxSize)})`;
      }
      return null;
    },
    [maxSize]
  );

  const uploadFiles = useCallback(
    async (filesToUpload: File[]) => {
      const uploadedFiles: UploadedFile[] = [];

      for (const file of filesToUpload) {
        try {
          const result = await uploadFile(file, fileType);
          const uploadedFile: UploadedFile = {
            id: Math.random().toString(36).substring(7),
            file,
            file_path: result.file_path,
            file_name: result.file_name,
            original_name: result.original_name,
            size: file.size,
            upload_time: new Date().toISOString(),
            file_type: file.type,
          };
          uploadedFiles.push(uploadedFile);
        } catch (error) {
          if (error instanceof ApiError) {
            setErrors((prev) => [...prev, `${file.name}: ${error.message}`]);
          } else {
            setErrors((prev) => [...prev, `${file.name}: 上传失败`]);
          }
        }
      }

      if (uploadedFiles.length > 0) {
        shouldNotifyFilesChangeRef.current = true;
        setFiles((prev) => (multiple ? [...prev, ...uploadedFiles] : uploadedFiles));
        onUpload?.(uploadedFiles);
      }
    },
    [fileType, multiple, onUpload]
  );

  const processFiles = useCallback(
    async (newFiles: FileList | null) => {
      if (!newFiles) return;

      const fileArray = Array.from(newFiles);
      const newErrors: string[] = [];

      // Validate files
      fileArray.forEach((file) => {
        const error = validateFile(file);
        if (error) {
          newErrors.push(`${file.name}: ${error}`);
        }
      });

      if (newErrors.length > 0) {
        setErrors(newErrors);
        return;
      }

      if (!multiple && fileArray.length > 1) {
        setErrors(['只能上传一个文件']);
        return;
      }

      if (multiple && files.length + fileArray.length > maxFiles) {
        setErrors([`最多只能上传 ${maxFiles} 个文件`]);
        return;
      }

      setErrors([]);

      // Call onFileSelect if provided (for non-auto-upload mode)
      if (onFileSelect) {
        onFileSelect(fileArray);
      }

      // Auto upload if enabled
      if (autoUpload) {
        await uploadFiles(fileArray);
      }
    },
    [autoUpload, files.length, maxFiles, multiple, onFileSelect, uploadFiles, validateFile]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      if (disabled) {
        return;
      }
      processFiles(e.dataTransfer.files);
    },
    [disabled, processFiles]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      processFiles(e.target.files);
      // Reset input value to allow re-uploading the same file
      e.target.value = '';
    },
    [processFiles]
  );

  const removeFile = useCallback(
    (id: string) => {
      shouldNotifyFilesChangeRef.current = true;
      setFiles((prev) => prev.filter((f) => f.id !== id));
    },
    []
  );
  const selectionHint = multiple ? `最多 ${maxFiles} 个文件` : '单文件上传';

  return (
    <div className={cn('space-y-3', className)}>
      {/* Upload Area */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={cn(
          'relative cursor-pointer rounded-xl border border-dashed px-4 py-3.5 transition-all',
          'hover:border-[var(--primary)] hover:bg-[var(--primary)]/5 hover:shadow-sm',
          isDragging && 'border-[var(--primary)] bg-[var(--primary)]/10 shadow-sm',
          disabled && 'cursor-not-allowed opacity-50'
        )}
      >
        <input
          type="file"
          accept={accept}
          multiple={multiple}
          onChange={handleFileInput}
          disabled={disabled}
          className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
        />
        <div className="flex flex-col gap-3 text-center sm:flex-row sm:items-center sm:justify-between sm:text-left">
          <div className="flex flex-col items-center gap-3 sm:flex-row">
            <div className="mx-auto flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[var(--primary)]/10 text-[var(--primary)] sm:mx-0">
              <Upload className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold text-[var(--foreground)]">{label}</p>
              <p className="mt-1 text-xs leading-5 text-[var(--text-muted)]">{description}</p>
            </div>
          </div>
          <div className="inline-flex items-center justify-center rounded-full border border-[var(--primary)]/15 bg-[var(--primary)]/8 px-3 py-1.5 text-xs font-medium text-[var(--primary)]">
            点击或拖拽上传
          </div>
        </div>
        <p className="mt-3 text-center text-[11px] text-[var(--text-muted)] sm:text-left">
          {selectionHint}
        </p>
      </div>

      {/* Error Messages */}
      {errors.length > 0 && (
        <div className="space-y-2">
          {errors.map((error, index) => (
            <div
              key={index}
              className="flex items-center gap-2 rounded-xl bg-red-50 px-3 py-2 text-xs text-red-600"
            >
              <AlertCircle className="h-4 w-4" />
              {error}
            </div>
          ))}
        </div>
      )}

      {/* File List */}
      {files.length > 0 && (
        <div className="space-y-2">
          {files.map((file) => (
            <div
              key={file.id}
              className={cn(
                'flex items-center justify-between rounded-xl border px-3 py-2.5 transition-colors',
                'border-green-200 bg-green-50/80'
              )}
            >
              <div className="flex min-w-0 items-center gap-2.5">
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-green-100">
                  <CheckCircle2 className="h-4 w-4 text-green-600" />
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-green-900">
                    {file.original_name}
                  </p>
                  <p className="text-xs text-green-600">{formatFileSize(file.size)} · 上传成功</p>
                </div>
              </div>
              <button
                onClick={() => removeFile(file.id)}
                disabled={disabled}
                className="rounded p-1 text-green-600 transition-colors hover:bg-green-100 hover:text-green-800 disabled:opacity-50"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
