import { Component } from "react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, info: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    this.setState({ info });
    // Log to console; swap for a real error-tracking service (Sentry, etc.) later
    console.error("[ErrorBoundary]", error, info?.componentStack);
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    const isDev = import.meta.env.DEV;

    return (
      <div className="min-h-screen bg-[#F7F7FC] flex items-center justify-center px-4 font-['Inter',sans-serif]">
        <div className="w-full max-w-md bg-white rounded-2xl border border-[#F0F2F7] shadow-lg p-10 text-center">
          {/* Icon */}
          <div className="w-16 h-16 bg-[#FFEDED] rounded-2xl flex items-center justify-center mx-auto mb-6">
            <span className="text-3xl">⚠️</span>
          </div>

          <h1 className="text-[22px] font-bold text-[#1A1E2E] mb-2">
            Something went wrong
          </h1>
          <p className="text-[14px] text-[#737A8F] mb-8">
            An unexpected error occurred. Your session and data are safe.
          </p>

          <div className="flex flex-col gap-3">
            <button
              onClick={() => window.location.reload()}
              className="w-full h-12 bg-[#1A78F2] hover:bg-[#1259C8] text-white font-semibold text-[14px] rounded-xl transition"
            >
              Reload Page
            </button>
            <button
              onClick={() => { window.location.href = "/login"; }}
              className="w-full h-12 bg-white border border-[#E2E6F0] text-[#404454] font-medium text-[14px] rounded-xl transition hover:bg-[#F7F7FC]"
            >
              Go to Login
            </button>
          </div>

          {isDev && this.state.error && (
            <details className="mt-6 text-left">
              <summary className="text-[12px] text-[#737A8F] cursor-pointer select-none hover:text-[#1A1E2E] transition">
                Developer details ▸
              </summary>
              <pre className="mt-3 text-[11px] bg-[#F0F2F7] rounded-lg p-4 overflow-auto text-[#EE3B3B] whitespace-pre-wrap break-words">
                {this.state.error.toString()}
                {"\n\n"}
                {this.state.info?.componentStack}
              </pre>
            </details>
          )}
        </div>
      </div>
    );
  }
}
