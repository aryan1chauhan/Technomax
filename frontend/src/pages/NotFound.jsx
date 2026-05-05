import { useNavigate } from "react-router-dom";

export default function NotFound() {
  const navigate = useNavigate();

  const role = localStorage.getItem("role");
  const homeRoute =
    role === "hospital"  ? "/hospital/dashboard" :
    role === "ambulance" ? "/dispatch"           :
    role === "admin"     ? "/admin/dashboard"    :
    "/login";

  return (
    <div className="min-h-screen bg-[#0D1830] flex items-center justify-center px-4 font-['Inter',sans-serif]">
      {/* Decorative background rings */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full border border-[#172954] animate-pulse" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] rounded-full border border-[#172954]" />
      </div>

      <div className="relative z-10 text-center">
        {/* Logo mark */}
        <div className="flex items-center justify-center gap-3 mb-12">
          <div className="relative w-10 h-10 bg-[#EE3B3B] rounded-xl flex items-center justify-center flex-shrink-0">
            <div className="absolute w-4 h-1.5 bg-white rounded-sm" />
            <div className="absolute w-1.5 h-4 bg-white rounded-sm" />
          </div>
          <span className="text-[22px] font-bold text-white">MediRoute</span>
        </div>

        {/* 404 number */}
        <div className="text-[120px] font-extrabold leading-none text-[#172954] select-none mb-2">
          404
        </div>

        {/* Red accent line */}
        <div className="w-16 h-1 bg-[#EE3B3B] rounded-full mx-auto mb-8" />

        <h1 className="text-[28px] font-bold text-white mb-3">
          Page not found
        </h1>
        <p className="text-[15px] text-[#737A8F] mb-10 max-w-sm mx-auto leading-relaxed">
          The route you're looking for doesn't exist or you don't have
          permission to access it.
        </p>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <button
            onClick={() => navigate(homeRoute)}
            className="px-8 py-3 bg-[#1A78F2] hover:bg-[#1259C8] text-white font-semibold text-[14px] rounded-xl transition"
          >
            Go to Dashboard
          </button>
          <button
            onClick={() => navigate(-1)}
            className="px-8 py-3 bg-[#172954] hover:bg-[#1e3470] text-[#C7CCD9] font-medium text-[14px] rounded-xl transition border border-[#172954]"
          >
            ← Go Back
          </button>
        </div>
      </div>
    </div>
  );
}
