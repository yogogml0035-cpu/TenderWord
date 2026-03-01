'use client';

import React, { useCallback, useState } from 'react';
import { cn, formatFileSize } from '@/lib/utils';
import { Upload, X, FileText, Check, AlertCircle } from 'lucide-react';

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
  fileType?: string;
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
  uploadEndpoint = '/api/upload',
  fileType,
}: FileUploaderProps) {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validateFiles = useCallback(
    (fileList: FileList): File[] => {
      const validFiles: File[] = [];
      const acceptedTypes = accept.split(',').map((t) => t.trim().toLowerCase());

      for (let i = 0; i < fileList.length; i++) {
        const file = fileList[i];
        const extension = `.${file.name.split('.').pop()?.toLowerCase()}`;

        if (!acceptedTypes.includes(extension)) {
          setError(`不支持的文件类型：${file.name}`);
          continue;
        }

        if (file.size > maxSize) {
          setError(`文件过大：${file.name} (最大 ${formatFileSize(maxSize)})`);
          continue;
        }

        validFiles.push(file);
      }

      if (!multiple && validFiles.length > 1) {
        return [validFiles[0]];
      }

      if (validFiles.length > maxFiles) {
        setError(`最多上传 ${maxFiles} 个文件`);
        return validFiles.slice(0, maxFiles);
      }

      return validFiles;
    },
    [accept, maxSize, maxFiles, multiple]
  );

  const uploadFiles = useCallback(
    async (filesToUpload: File[]): Promise<UploadedFile[]> => {
      if (filesToUpload.length === 0) return [];

      setIsUploading(true);
      setError(null);

      try {
        const uploadedFiles: UploadedFile[] = [];

        for (const file of filesToUpload) {
          const formData = new FormData();
          formData.append('file', file);
          if (fileType) {
            formData.append('file_type', fileType);
          }

          const response = await fetch(uploadEndpoint, {
            method: 'POST',
            body: formData,
          });

          const result = await response.json();

          if (!response.ok || !result.success) {
            throw new Error(result.error?.message || `上传失败：${file.name}`);
          }

          const uploadedFile: UploadedFile = {
            id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            file,
            ...result.data,
          };

          uploadedFiles.push(uploadedFile);
        }

        setFiles((prev) => (multiple ? [...prev, ...uploadedFiles] : uploadedFiles));
        onUpload?.(uploadedFiles);

        return uploadedFiles;
      } catch (err) {
        setError(err instanceof Error ? err.message : '上传失败');
        return [];
      } finally {
        setIsUploading(false);
      }
    },
    [uploadEndpoint, fileType, multiple, onUpload]
  );

  const handleFileSelect = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const fileList = e.target.files;
      if (!fileList || fileList.length === 0) return;

      const validFiles = validateFiles(fileList);
      if (validFiles.length === 0) return;

      onFileSelect?.(validFiles);

      if (autoUpload) {
        await uploadFiles(validFiles);
      } else {
        // Create local file objects without uploading
        const localFiles: UploadedFile[] = validFiles.map((file) => ({
          id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          file,
          file_path: '',
          file_name: file.name,
          original_name: file.name,
          size: file.size,
          upload_time: new Date().toISOString(),
          file_type: fileType,
        }));

        setFiles((prev) => (multiple ? [...prev, ...localFiles] : localFiles));
      }

      // Reset input
      e.target.value = '';
    },
    [validateFiles, autoUpload, uploadFiles, onFileSelect, multiple, fileType]
  );

  const handleDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);

      if (disabled || isUploading) return;

      const fileList = e.dataTransfer.files;
      if (!fileList || fileList.length === 0) return;

      const validFiles = validateFiles(fileList);
      if (validFiles.length === 0) return;

      onFileSelect?.(validFiles);

      if (autoUpload) {
        await uploadFiles(validFiles);
      } else {
        const localFiles: UploadedFile[] = validFiles.map((file) => ({
          id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          file,
          file_path: '',
          file_name: file.name,
          original_name: file.name,
          size: file.size,
          upload_time: new Date().toISOString(),
          file_type: fileType,
        }));

        setFiles((prev) => (multiple ? [...prev, ...localFiles] : localFiles));
      }
    },
    [disabled, isUploading, validateFiles, autoUpload, uploadFiles, onFileSelect, multiple, fileType]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled && !isUploading) {
      setIsDragging(true);
    }
  }, [disabled, isUploading]);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const removeFile = useCallback(
    (id: string) => {
      setFiles((prev) => prev.filter((f) => f.id !== id));
    },
    []
  );

  const clearAll = useCallback(() => {
    setFiles([]);
    setError(null);
  }, []);

  const handleManualUpload = useCallback(async () => {
    const filesToUpload = files.filter((f) => !f.file_path);
    if (filesToUpload.length === 0) return;

    const uploaded = await uploadFiles(filesToUpload.map((f) => f.file));

    // Update file paths for uploaded files
    setFiles((prev) =>
      prev.map((f) => {
        const uploadedFile = uploaded.find((u) => u.original_name === f.original_name);
        return uploadedFile ? { ...f, ...uploadedFile } : f;
      })
    );
  }, [files, uploadFiles]);

  return (
    <div className={cn('space-y-3', className)}>
      <label className="block text-sm font-medium text-[var(--foreground)]">
        {label}
        {multiple && maxFiles > 1 && (
          <span className="text-[var(--text-muted)] ml-1">(最多 {maxFiles} 个)</span>
        )}
      </label>

      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={cn(
          'border-2 border-dashed rounded-lg p-6 text-center transition-colors',
          isDragging
            ? 'border-[var(--primary)] bg-[var(--primary)]/5'
            : 'border-[var(--border)] hover:border-[var(--primary)]/50',
          (disabled || isUploading) && 'opacity-50 cursor-not-allowed'
        )}
      >
        <input
          type="file"
          accept={accept}
          multiple={multiple}
          onChange={handleFileSelect}
          disabled={disabled || isUploading}
          className="hidden"
          id={`file-upload-${label}`}
        />
        <label
          htmlFor={`file-upload-${label}`}
          className={cn(
            'cursor-pointer flex flex-col items-center gap-2',
            (disabled || isUploading) && 'cursor-not-allowed'
          )}
        >
          <div className="p-3 bg-[var(--secondary-bg)] rounded-full">
            <Upload className="w-6 h-6 text-[var(--text-muted)]" />
          </div>
          <div>
            <p className="text-sm font-medium text-[var(--foreground)]">
              点击或拖拽文件到此处上传
            </p>
            <p className="text-xs text-[var(--text-muted)] mt-1">{description}</p>
          </div>
        </label>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-sm text-[var(--error)]">
          <AlertCircle className="w-4 h-4" />
          {error}
        </div>
      )}

      {files.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-[var(--foreground)]">
              已选择 {files.length} 个文件
            </p>
            <div className="flex gap-2">
              {!autoUpload && files.some((f) => !f.file_path) && (
                <button
                  type="button"
                  onClick={handleManualUpload}
                  disabled={isUploading}
                  className="text-xs px-2 py-1 bg-[var(--primary)] text-white rounded hover:bg-[var(--primary-hover)] disabled:opacity-50"
                >
                  {isUploading ? '上传中...' : '上传'}
                </button>
              )}
              <button
                type="button"
                onClick={clearAll}
                disabled={isUploading}
                className="text-xs text-[var(--text-muted)] hover:text-[var(--error)]"
              >
                清空
              </button>
            </div>
          </div>

          <div className="space-y-2">
            {files.map((file) => (
              <div
                key={file.id}
                className="flex items-center gap-3 p-3 bg-[var(--secondary-bg)] rounded-lg"
              >
                <FileText className="w-5 h-5 text-[var(--primary)] flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-[var(--foreground)] truncate">
                    {file.original_name}
                  </p>
                  <p className="text-xs text-[var(--text-muted)]">
                    {formatFileSize(file.size)}
                    {file.file_path && (
                      <span className="ml-2 text-[var(--success)] flex items-center gap-1 inline-flex">
                        <Check className="w-3 h-3" /> 已上传
                      </span>
                    )}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => removeFile(file.id)}
                  disabled={isUploading}
                  className="p-1 text-[var(--text-muted)] hover:text-[var(--error)] transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default FileUploader;
