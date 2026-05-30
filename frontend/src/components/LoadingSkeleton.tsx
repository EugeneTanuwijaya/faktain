"use client";

export default function LoadingSkeleton() {
  return (
    <div className="rule-top rule-bottom py-6 mb-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="skeleton h-8 w-48 rounded-none" />
        <div className="skeleton h-10 w-16 rounded-none" />
      </div>
      <div className="space-y-3 mb-6">
        <div className="skeleton h-4 w-full rounded-none" />
        <div className="skeleton h-4 w-4/5 rounded-none" />
        <div className="skeleton h-4 w-3/5 rounded-none" />
      </div>
      <div className="rule-top pt-4">
        <div className="skeleton h-5 w-40 rounded-none mb-3" />
        <div className="space-y-2">
          <div className="skeleton h-3 w-full rounded-none" />
          <div className="skeleton h-3 w-5/6 rounded-none" />
          <div className="skeleton h-3 w-4/6 rounded-none" />
        </div>
      </div>
      <p className="meta-text mt-6 text-center animate-pulse">
        Sedang menganalisis dengan AI... Mohon tunggu 10-30 detik.
      </p>
    </div>
  );
}
