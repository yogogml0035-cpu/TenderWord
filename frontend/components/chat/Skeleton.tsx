'use client';

import React from 'react';

interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className = '' }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse bg-gradient-to-r from-gray-200 via-gray-100 to-gray-200 bg-[length:200%_100%] ${className}`}
      style={{
        animation: 'shimmer 1.5s infinite',
      }}
    />
  );
}

// Message skeleton for loading states
export function MessageSkeleton() {
  return (
    <div className="flex gap-3">
      <div className="flex-shrink-0">
        <Skeleton className="w-8 h-8 rounded-full" />
      </div>
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-3/4 rounded" />
        <Skeleton className="h-4 w-1/2 rounded" />
        <Skeleton className="h-20 w-full rounded-lg" />
      </div>
    </div>
  );
}

// Form field skeleton
export function FormFieldSkeleton() {
  return (
    <div className="space-y-2">
      <Skeleton className="h-4 w-24 rounded" />
      <Skeleton className="h-10 w-full rounded-lg" />
    </div>
  );
}

// Dual column message skeleton
export function DualColumnSkeleton() {
  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b border-gray-200">
        <Skeleton className="h-4 w-20 rounded" />
        <Skeleton className="h-6 w-24 rounded" />
      </div>
      
      {/* Content */}
      <div className="flex" style={{ height: '300px' }}>
        {/* Left Column */}
        <div className="w-1/2 border-r border-gray-200 p-3 space-y-2">
          <Skeleton className="h-3 w-full rounded" />
          <Skeleton className="h-3 w-5/6 rounded" />
          <Skeleton className="h-3 w-4/5 rounded" />
          <Skeleton className="h-3 w-full rounded" />
          <Skeleton className="h-3 w-3/4 rounded" />
        </div>
        
        {/* Right Column */}
        <div className="w-1/2 p-3 space-y-2">
          <Skeleton className="h-3 w-full rounded" />
          <Skeleton className="h-3 w-5/6 rounded" />
          <Skeleton className="h-3 w-4/5 rounded" />
          <Skeleton className="h-3 w-full rounded" />
          <Skeleton className="h-3 w-3/4 rounded" />
        </div>
      </div>
    </div>
  );
}

// Full page skeleton for initial load
export function PageSkeleton() {
  return (
    <div className="flex h-full">
      {/* Sidebar skeleton */}
      <div className="w-64 bg-gray-50 p-4 space-y-4 border-r border-gray-200">
        <Skeleton className="h-8 w-full rounded-lg" />
        <div className="space-y-2">
          <Skeleton className="h-12 w-full rounded-lg" />
          <Skeleton className="h-12 w-full rounded-lg" />
          <Skeleton className="h-12 w-full rounded-lg" />
        </div>
      </div>
      
      {/* Main content skeleton */}
      <div className="flex-1 p-4 space-y-4">
        <Skeleton className="h-16 w-full rounded-lg" />
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-4">
            <FormFieldSkeleton />
            <FormFieldSkeleton />
            <FormFieldSkeleton />
          </div>
          <div className="space-y-4">
            <MessageSkeleton />
            <MessageSkeleton />
          </div>
        </div>
      </div>
    </div>
  );
}

export default Skeleton;
