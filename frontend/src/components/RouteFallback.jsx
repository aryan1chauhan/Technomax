export default function RouteFallback({ label = "Loading..." }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#F7F7FC] px-6">
      <div className="flex items-center gap-3 rounded-xl border border-[#E2E6F0] bg-white px-5 py-4 text-[#4A5068] shadow-sm">
        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-[#D0D5E8] border-t-[#1A78F2]" />
        <span className="text-sm font-medium">{label}</span>
      </div>
    </div>
  );
}
