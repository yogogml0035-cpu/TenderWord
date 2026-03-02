'use client';

import React, { useCallback, useState } from 'react';
import { cn, formatFileSize } from '@/lib/utils';
import { Upload, X, FileText, Check, AlertCircle } from 'lucide-react';
import { uploadFile, ApiError } from '@/lib/api';
import type { UploadedFile as ApiUploadedFile, FileType } from '@/types/api';

export interface UploadedFile {
  id: string;
  file: File;
  file_path: string;
  file_name: string;
  original_name: string;
  size: number;
  upload_time: string;
  file_type?: string;
}

export interface FileUploaderProps {
  onUpload?: (files: UploadedFile[]) => void;
  onFileSelect?: (files: File[]) => void;
  multiple?: boolean;
  accept?: string;
  maxFiles?: number;
  maxSize?: number; // in bytes
  label?: string;
  description?: string;
  disabled?: boolean;
  className?: string;
  autoUpload?: boolean;
  uploadEndpoint?: string;
  fileType?: FileType;
}

export function FileUploader({
  onUpload,
  onFileSelect,
  multiple = false,
  accept = '.doc,.docx',
  maxFiles = 10,
  maxSize = 50 * 1024 * 1024, // 50MB
  label = '上传文件',
  description = '支持 .doc, .docx 格式',
  disabled = false,
  className,
  autoUpload = false,
  uploadEndpoint,
  fileType,
}: FileUploaderProps) {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const validateFile = (file: File): string | null => {
    if (maxSize && file.size > maxSize) {
      return `文件大小超过限制 (最大 ${formatFileSize(maxSize)})`;
    }
    return null;
  };

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
      if (autoUpload && uploadEndpoint) {
        await uploadFiles(fileArray);
      }
    },
    [files.length, maxFiles, multiple, autoUpload, uploadEndpoint, onFileSelect]
  );

  const uploadFiles = async (filesToUpload: File[]) => {
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
      setFiles((prev) => (multiple ? [...prev, ...uploadedFiles] : uploadedFiles));
      onUpload?.(uploadedFiles);
    }
  };

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      processFiles(e.dataTransfer.files);
    },
    [processFiles]
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
      setFiles((prev) => prev.filter((f) => f.id !== id));
    },
    [setFiles]
  );

  return (
    <div className={cn('space-y-4', className)}>
      {/* Upload Area */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={cn(
          'relative border-2 border-dashed rounded-lg p-6 transition-colors cursor-pointer',
          'hover:border-[var(--primary)] hover:bg-[var(--primary)]/5',
          isDragging && 'border-[var(--primary)] bg-[var(--primary)]/10',
          disabled && 'opacity-50 cursor-not-allowed'
        )}
      >
        <input
          type="file"
          accept={accept}
          multiple={multiple}
          onChange={handleFileInput}
          disabled={disabled}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        />
        <div className="flex flex-col items-center justify-center text-center space-y-2">
          <Upload className="w-10 h-10 text-[var(--text-muted)]" />
          <div>
            <p className="text-sm font-medium text-[var(--foreground)]">{label}</p>
            <p className="text-xs text-[var(--text-muted)] mt-1">{description}</p>
          </div>
          <p className="text-xs text-[var(--text-muted)]">
            拖放文件到此处，或点击选择文件
          </p>
        </div>
      </div>

      {/* Error Messages */}
      {errors.length > 0 && (
        <div className="space-y-2">
          {errors.map((error, index) => (
            <div
              key={index}
              className="flex items-center gap-2 p-3 text-sm text-red-600 bg-red-50 rounded-lg"
            >
              <AlertCircle className="w-4 h-4" />
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
              className="flex items-center justify-between p-3 bg-white rounded-lg border border-[var(--border)]"
            >
              <div className="flex items-center gap-3 min-w-0">
                <FileText className="w-5 h-5 text-[var(--primary)] flex-shrink-0" />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-[var(--foreground)] truncate">
                    {file.original_name}
                  </p>
                  <p className="text-xs text-[var(--text-muted)]">
                    {formatFileSize(file.size)}
                  </p>
                </div>
              </div>
              <button
                onClick={() => removeFile(file.id)}
                disabled={disabled}
                className="p-1 text-[var(--text-muted)] hover:text-red-500 transition-colors disabled:opacity-50"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
