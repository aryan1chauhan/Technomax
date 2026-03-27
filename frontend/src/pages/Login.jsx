// frontend/src/pages/Login.jsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { jwtDecode } from "jwt-decode";
import api from "../api/axios";

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true); setError("");
    try {
      const res = await api.post("/api/auth/login", { email, password });
      const { access_token } = res.data;
      localStorage.setItem("token", access_token);
      const decoded = jwtDecode(access_token);
      const role = decoded.role || "ambulance";
      localStorage.setItem("role", role);
      if (role === "ambulance")  navigate("/dispatch");
      else if (role === "hospital") navigate("/hospital/dashboard");
      else if (role === "admin") navigate("/admin/dashboard");
    } catch {
      setError("Invalid email or password. Please try again.");
    } finally { setLoading(false); }
  };

  const stats = [
    { val: "188", label: "Hospitals",    accent: "#1A78F2" },
    { val: "6",   label: "Districts",    accent: "#17B86B" },
    { val: "15",  label: "ML Features",  accent: "#FFB21A" },
  ];

  return (
    <div className="flex h-screen w-screen overflow-hidden font-['Inter',sans-serif]">

      {/* ── Left Panel ── */}
      <div className="relative w-[600px] flex-shrink-0 bg-[#0D1830] flex flex-col overflow-hidden">
        {/* Blue gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-b from-[rgba(26,120,242,0.25)] to-transparent pointer-events-none" />

        <div className="relative z-10 flex flex-col h-full px-[52px] py-[52px]">
          {/* Logo */}
          <div className="flex items-center gap-4 mb-6">
            <div className="relative w-14 h-14 bg-[#EE3B3B] rounded-2xl flex items-center justify-center flex-shrink-0">
              <div className="absolute w-6 h-2 bg-white rounded-sm" />
              <div className="absolute w-2 h-6 bg-white rounded-sm" />
            </div>
            <div>
              <h1 className="text-[36px] font-bold text-white leading-tight">MediRoute</h1>
              <p className="text-[16px] text-[#C7CCD9]">Emergency Dispatch System</p>
            </div>
          </div>

          {/* Stat Cards */}
          <div className="mt-[140px] flex flex-col gap-5">
            {stats.map(({ val, label, accent }) => (
              <div key={label} className="relative w-[200px] h-[88px] bg-[#172954] rounded-xl overflow-hidden">
                <div className="absolute left-0 top-0 w-1 h-full rounded-xl" style={{ backgroundColor: accent }} />
                <div className="pl-6 pt-4">
                  <p className="text-[32px] font-bold text-white leading-none">{val}</p>
                  <p className="text-[13px] text-[#C7CCD9] mt-1">{label}</p>
                </div>
              </div>
            ))}
          </div>

          <p className="mt-auto text-[13px] text-[#737A8F]">Uttarakhand State Health Network</p>
        </div>
      </div>

      {/* ── Right Panel ── */}
      <div className="flex-1 bg-[#F7F7FC] flex items-center justify-center">
        <div className="w-[440px] bg-white rounded-[20px] border border-[#F0F2F7] shadow-lg p-10">
          <h2 className="text-[28px] font-bold text-[#1A1E2E]">Welcome back</h2>
          <p className="text-[15px] text-[#737A8F] mt-2 mb-8">Sign in to your MediRoute account</p>

          <form onSubmit={handleLogin} className="flex flex-col gap-5">
            <div>
              <label className="block text-[13px] font-medium text-[#404454] mb-2">
                Email address
              </label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                autoFocus
                className="w-full h-12 bg-[#F0F2F7] rounded-[10px] px-4 text-[14px] text-[#1A1E2E] placeholder-[#C7CCD9] outline-none focus:ring-2 focus:ring-[#1A78F2] transition"
              />
            </div>

            <div>
              <label className="block text-[13px] font-medium text-[#404454] mb-2">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="w-full h-12 bg-[#F0F2F7] rounded-[10px] px-4 text-[14px] text-[#1A1E2E] placeholder-[#C7CCD9] outline-none focus:ring-2 focus:ring-[#1A78F2] transition"
              />
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-600 text-[13px] rounded-lg px-4 py-3">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full h-[52px] bg-[#1A78F2] hover:bg-[#1259C8] disabled:opacity-60 text-white font-semibold text-[15px] rounded-xl transition mt-2"
            >
              {loading ? "Signing in..." : "Sign In"}
            </button>
          </form>

          <p className="text-center text-[12px] text-[#C7CCD9] mt-6">
            Demo: amb1@test.com &nbsp;·&nbsp; bhagwati@test.com &nbsp;·&nbsp; admin@test.com &nbsp;/&nbsp; test123
          </p>
        </div>
      </div>
    </div>
  );
}
