import { useEffect, useRef, useState, useCallback } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { API_BASE } from "@/lib/api";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign In | SS Spark" },
      { name: "description", content: "Sign in to SS Spark — AI Question Paper Analyzer" },
    ],
  }),
  component: LoginPage,
});

// Particle system
type Particle = {
  x: number; y: number; vx: number; vy: number;
  size: number; alpha: number; hue: number; life: number; maxLife: number;
};

function ParticleCanvas({ mouseX, mouseY }: { mouseX: number; mouseY: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const particlesRef = useRef<Particle[]>([]);
  const mouseRef = useRef({ x: 0.5, y: 0.5 });
  useEffect(() => { mouseRef.current = { x: mouseX, y: mouseY }; }, [mouseX, mouseY]);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const resize = () => { canvas.width = window.innerWidth; canvas.height = window.innerHeight; };
    resize();
    window.addEventListener("resize", resize);
    const count = Math.min(110, Math.floor((window.innerWidth * window.innerHeight) / 14000));
    particlesRef.current = Array.from({ length: count }, () => ({
      x: Math.random() * window.innerWidth, y: Math.random() * window.innerHeight,
      vx: (Math.random() - 0.5) * 0.22, vy: (Math.random() - 0.5) * 0.22 - 0.08,
      size: Math.random() * 1.6 + 0.3, alpha: Math.random() * 0.55 + 0.1,
      hue: Math.random() < 0.6 ? 200 + Math.random() * 40 : 270 + Math.random() * 30,
      life: Math.random() * 300, maxLife: 200 + Math.random() * 300,
    }));
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const mx = mouseRef.current.x * canvas.width;
      const my = mouseRef.current.y * canvas.height;
      particlesRef.current.forEach((p) => {
        p.life++;
        if (p.life > p.maxLife) {
          p.x = Math.random() * canvas.width; p.y = canvas.height + 10;
          p.life = 0; p.maxLife = 200 + Math.random() * 300;
          p.vx = (Math.random() - 0.5) * 0.22; p.vy = -Math.random() * 0.35 - 0.05;
        }
        const dx = mx - p.x; const dy = my - p.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 180 && dist > 0) { p.vx += (dx / dist) * 0.003; p.vy += (dy / dist) * 0.003; }
        p.vx *= 0.992; p.vy *= 0.992; p.x += p.vx; p.y += p.vy;
        const currentAlpha = p.alpha * Math.sin((p.life / p.maxLife) * Math.PI);
        ctx.beginPath(); ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${p.hue}, 90%, 75%, ${currentAlpha})`; ctx.fill();
      });
      animRef.current = requestAnimationFrame(draw);
    };
    draw();
    return () => { cancelAnimationFrame(animRef.current); window.removeEventListener("resize", resize); };
  }, []);
  return <canvas ref={canvasRef} style={{ position: "fixed", inset: 0, pointerEvents: "none", zIndex: 1 }} />;
}

// 3D Energy Core
function EnergyCore({ mouseX, mouseY }: { mouseX: number; mouseY: number }) {
  const rotX = (mouseY - 0.5) * -16;
  const rotY = (mouseX - 0.5) * 16;
  return (
    <div style={{ position: "relative", width: 280, height: 280, transformStyle: "preserve-3d", transform: `rotateX(${rotX}deg) rotateY(${rotY}deg)`, transition: "transform 0.14s ease-out" }}>
      {[1, 2, 3].map((i) => (
        <div key={i} style={{ position: "absolute", inset: `${i * 14}px`, borderRadius: "50%", border: `1px solid rgba(56,189,248,${0.22 - i * 0.05})`, animation: `coreRingPulse ${2.5 + i * 0.7}s ease-in-out infinite`, animationDelay: `${i * 0.4}s` }} />
      ))}
      <div style={{ position: "absolute", inset: "28px", borderRadius: "50%", border: "1px solid rgba(139,92,246,0.4)", transform: "rotateX(75deg)", animation: "orbitSpin1 8s linear infinite", boxShadow: "0 0 12px rgba(139,92,246,0.3), inset 0 0 12px rgba(139,92,246,0.1)" }} />
      <div style={{ position: "absolute", inset: "18px", borderRadius: "50%", border: "1px solid rgba(56,189,248,0.32)", transform: "rotateX(65deg) rotateZ(45deg)", animation: "orbitSpin2 11s linear infinite reverse", boxShadow: "0 0 10px rgba(56,189,248,0.25)" }} />
      <div style={{ position: "absolute", top: "50%", left: "50%", width: 118, height: 118, marginLeft: -59, marginTop: -59, animation: "coreFloat 6s ease-in-out infinite, coreRotate 22s linear infinite" }}>
        <div style={{ position: "absolute", inset: 0, background: "radial-gradient(ellipse at 35% 35%, rgba(186,230,253,0.9) 0%, rgba(56,189,248,0.75) 30%, rgba(99,102,241,0.4) 65%, transparent 100%)", clipPath: "polygon(50% 0%, 80% 35%, 100% 50%, 80% 65%, 50% 100%, 20% 65%, 0% 50%, 20% 35%)", filter: "drop-shadow(0 0 22px rgba(56,189,248,0.9)) drop-shadow(0 0 44px rgba(99,102,241,0.5))" }} />
        <div style={{ position: "absolute", inset: "12px", background: "linear-gradient(135deg, rgba(255,255,255,0.28) 0%, rgba(56,189,248,0.12) 50%, transparent 100%)", clipPath: "polygon(50% 0%, 80% 35%, 100% 50%, 80% 65%, 50% 100%, 20% 65%, 0% 50%, 20% 35%)" }} />
      </div>
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <div key={i} style={{ position: "absolute", top: "50%", left: "50%", width: 5, height: 5, marginLeft: -2.5, marginTop: -2.5, borderRadius: "50%", background: i % 2 === 0 ? "rgba(56,189,248,0.9)" : "rgba(167,139,250,0.9)", boxShadow: i % 2 === 0 ? "0 0 6px rgba(56,189,248,0.8)" : "0 0 6px rgba(167,139,250,0.8)", animation: `orbitParticle${(i % 3) + 1} ${5 + i * 0.7}s linear infinite`, animationDelay: `${i * -1.2}s`, transformOrigin: `${100 + (i % 2 === 0 ? 82 : 98)}px ${i % 2 === 0 ? 82 : 98}px` }} />
      ))}
      <div style={{ position: "absolute", top: "50%", left: "50%", width: 180, height: 180, marginLeft: -90, marginTop: -90, borderRadius: "50%", background: "radial-gradient(circle, rgba(56,189,248,0.11) 0%, rgba(99,102,241,0.07) 50%, transparent 70%)", animation: "coreGlowPulse 3s ease-in-out infinite", filter: "blur(8px)" }} />
    </div>
  );
}

function LoginPage() {
  const navigate = useNavigate();
  const { login, setGuest, isAuthenticated, isAdmin } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [mouseX, setMouseX] = useState(0.5);
  const [mouseY, setMouseY] = useState(0.5);
  const [entered, setEntered] = useState(false);
  const [btnPulse, setBtnPulse] = useState(false);
  const pageRef = useRef<HTMLDivElement>(null);

  useEffect(() => { const t = setTimeout(() => setEntered(true), 80); return () => clearTimeout(t); }, []);

  // Redirect if already logged in
  useEffect(() => {
    if (isAuthenticated) { if (isAdmin) navigate({ to: "/admin" }); else navigate({ to: "/" }); }
  }, [isAuthenticated, isAdmin, navigate]);

  // Show OAuth error messages passed back from backend redirect (?error=...)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const oauthError = params.get("error");
    if (oauthError) { toast.error(decodeURIComponent(oauthError)); window.history.replaceState(null, "", window.location.pathname); }
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const rect = pageRef.current?.getBoundingClientRect();
    if (!rect) return;
    setMouseX((e.clientX - rect.left) / rect.width);
    setMouseY((e.clientY - rect.top) / rect.height);
  }, []);

  const validate = () => {
    const newErrors: { email?: string; password?: string } = {};
    if (!email) newErrors.email = "Email is required";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) newErrors.email = "Enter a valid email";
    if (!password) newErrors.password = "Password is required";
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setBtnPulse(true);
    setTimeout(() => setBtnPulse(false), 650);
    setIsLoading(true);
    try {
      await login(email, password);
      toast.success("Welcome back!");
      // navigate happens via isAuthenticated check above
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Login failed");
    } finally {
      setIsLoading(false);
    }
  };

  const handleOAuthClick = async (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/api/health`);
      if (!res.ok) throw new Error("Backend unavailable");
      window.location.href = `${API_BASE}/api/auth/oauth/google`;
    } catch {
      toast.error(`Cannot connect to backend server at ${API_BASE}. Please ensure the FastAPI server is running.`);
    }
  };

  const handleGuest = () => {
    setGuest();
    toast("Browsing as guest — uploads and chats won't be saved.");
    navigate({ to: "/" });
  };

  const px = (mouseX - 0.5) * 18;
  const py = (mouseY - 0.5) * 10;

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;600;700;800&display=swap');
        @keyframes coreFloat { 0%,100%{transform:translateY(0) scale(1)} 50%{transform:translateY(-13px) scale(1.04)} }
        @keyframes coreRotate { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
        @keyframes coreRingPulse { 0%,100%{opacity:.5;transform:scale(1)} 50%{opacity:1;transform:scale(1.04)} }
        @keyframes coreGlowPulse { 0%,100%{opacity:.55;transform:scale(1)} 50%{opacity:1;transform:scale(1.14)} }
        @keyframes orbitSpin1 { from{transform:rotateX(75deg) rotateZ(0deg)} to{transform:rotateX(75deg) rotateZ(360deg)} }
        @keyframes orbitSpin2 { from{transform:rotateX(65deg) rotateZ(45deg)} to{transform:rotateX(65deg) rotateZ(405deg)} }
        @keyframes orbitParticle1 { from{transform:rotate(0deg) translateX(82px)} to{transform:rotate(360deg) translateX(82px)} }
        @keyframes orbitParticle2 { from{transform:rotate(0deg) translateX(102px)} to{transform:rotate(360deg) translateX(102px)} }
        @keyframes orbitParticle3 { from{transform:rotate(0deg) translateX(68px)} to{transform:rotate(360deg) translateX(68px)} }
        @keyframes lp-brand { 0%{opacity:0;letter-spacing:.28em;transform:translateY(-18px)} 100%{opacity:1;letter-spacing:.05em;transform:translateY(0)} }
        @keyframes lp-panel { 0%{opacity:0;transform:translateX(38px) scale(.97)} 100%{opacity:1;transform:translateX(0) scale(1)} }
        @keyframes lp-scene { 0%{opacity:0;transform:translateX(-28px)} 100%{opacity:1;transform:translateX(0)} }
        @keyframes lp-fade { 0%{opacity:0} 100%{opacity:1} }
        @keyframes lp-btnpulse { 0%{box-shadow:0 0 0 0 rgba(56,189,248,.75)} 70%{box-shadow:0 0 0 14px rgba(56,189,248,0)} 100%{box-shadow:0 0 0 0 rgba(56,189,248,0)} }
        @keyframes lp-vol { 0%,100%{opacity:.055;transform:scale(1)} 50%{opacity:.11;transform:scale(1.08)} }
        @keyframes lp-spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
        .lp-input{width:100%;box-sizing:border-box;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:12px 16px;color:#f0f9ff;font-size:14px;font-family:'Inter',sans-serif;outline:none;transition:border-color .2s,background .2s,box-shadow .2s}
        .lp-input::placeholder{color:rgba(186,230,253,.3)}
        .lp-input:focus{border-color:rgba(56,189,248,.55);background:rgba(56,189,248,.05);box-shadow:0 0 0 3px rgba(56,189,248,.1)}
        .lp-err{border-color:rgba(239,68,68,.6)!important}
        .lp-field:focus-within .lp-lbl{color:rgba(56,189,248,.9)!important}
        .lp-google{display:flex;width:100%;box-sizing:border-box;align-items:center;justify-content:center;gap:10px;padding:11px 18px;border-radius:10px;border:1px solid rgba(255,255,255,.12);background:rgba(255,255,255,.05);color:rgba(240,249,255,.85);font-size:13.5px;font-weight:500;cursor:pointer;transition:all .2s ease;text-decoration:none;font-family:'Inter',sans-serif;backdrop-filter:blur(4px)}
        .lp-google:hover{background:rgba(255,255,255,.09);border-color:rgba(255,255,255,.22);transform:translateY(-1px);box-shadow:0 6px 20px rgba(0,0,0,.3)}
        @media(min-width:900px){.lp-scene-col{display:flex!important}}
      `}</style>

      <div ref={pageRef} onMouseMove={handleMouseMove} style={{ minHeight:"100vh", width:"100%", overflow:"hidden", position:"relative", fontFamily:"'Inter',sans-serif", background:"#050608", opacity: entered ? 1 : 0, animation: entered ? "lp-fade 1.1s ease-out forwards" : "none" }}>

        {/* Atmospheric bg */}
        <div style={{ position:"fixed", inset:0, pointerEvents:"none", zIndex:0, background:"radial-gradient(ellipse 80% 60% at 28% 58%, rgba(99,102,241,.07) 0%, transparent 60%), radial-gradient(ellipse 60% 50% at 74% 38%, rgba(56,189,248,.05) 0%, transparent 55%)" }} />

        {/* Volumetric lights */}
        <div style={{ position:"fixed", inset:0, pointerEvents:"none", zIndex:0 }}>
          <div style={{ position:"absolute", top:"12%", left:"10%", width:580, height:580, borderRadius:"50%", background:"radial-gradient(circle, rgba(99,102,241,.06) 0%, transparent 70%)", animation:"lp-vol 8s ease-in-out infinite", filter:"blur(40px)", transform:`translate(${px*.28}px,${py*.28}px)`, transition:"transform .16s ease-out" }} />
          <div style={{ position:"absolute", top:"45%", right:"8%", width:480, height:480, borderRadius:"50%", background:"radial-gradient(circle, rgba(56,189,248,.05) 0%, transparent 70%)", animation:"lp-vol 11s ease-in-out infinite 2.2s", filter:"blur(48px)", transform:`translate(${-px*.18}px,${-py*.18}px)`, transition:"transform .16s ease-out" }} />
        </div>

        {/* Scan lines */}
        <div style={{ position:"fixed", inset:0, pointerEvents:"none", zIndex:2, backgroundImage:"repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(56,189,248,.011) 2px, rgba(56,189,248,.011) 4px)" }} />

        <ParticleCanvas mouseX={mouseX} mouseY={mouseY} />

        <div style={{ position:"relative", zIndex:10, minHeight:"100vh", display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", padding:"24px 20px" }}>

          {/* Brand */}
          <div style={{ textAlign:"center", marginBottom:40, animation: entered ? "lp-brand 1s cubic-bezier(.16,1,.3,1) .25s both" : "none" }}>
            <div style={{ display:"inline-flex", alignItems:"center", gap:10, marginBottom:6 }}>
              <div style={{ width:36, height:36, borderRadius:10, background:"linear-gradient(135deg, rgba(56,189,248,.28) 0%, rgba(99,102,241,.38) 100%)", border:"1px solid rgba(56,189,248,.38)", display:"flex", alignItems:"center", justifyContent:"center", boxShadow:"0 0 18px rgba(56,189,248,.22), inset 0 0 10px rgba(56,189,248,.08)" }}>
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" fill="rgba(56,189,248,.92)" stroke="rgba(186,230,253,.45)" strokeWidth="1" /></svg>
              </div>
              <span style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:27, fontWeight:800, letterSpacing:".05em", color:"#f0f9ff" }}>
                SS <span style={{ background:"linear-gradient(90deg,#38bdf8 0%,#818cf8 100%)", WebkitBackgroundClip:"text", WebkitTextFillColor:"transparent" }}>SPARK</span>
              </span>
            </div>
            <p style={{ color:"rgba(186,230,253,.38)", fontSize:11, letterSpacing:".2em", textTransform:"uppercase", fontWeight:500 }}>AI Question Intelligence</p>
          </div>

          <div style={{ display:"flex", alignItems:"center", justifyContent:"center", gap:60, width:"100%", maxWidth:960 }}>

            {/* 3D scene – desktop only */}
            <div className="lp-scene-col" style={{ display:"none", flexDirection:"column", alignItems:"center", gap:26, animation: entered ? "lp-scene 1.2s cubic-bezier(.16,1,.3,1) .45s both" : "none" }}>
              <div style={{ perspective:"780px", perspectiveOrigin:"50% 50%" }}>
                <EnergyCore mouseX={mouseX} mouseY={mouseY} />
              </div>
              <div style={{ textAlign:"center", maxWidth:230 }}>
                <p style={{ color:"rgba(186,230,253,.42)", fontSize:13, lineHeight:1.65 }}>Upload question papers.<br />Ask anything. Get cited answers.</p>
                <div style={{ display:"flex", gap:8, justifyContent:"center", marginTop:15 }}>
                  {[{ v:"98.4%", l:"Accuracy" }, { v:"<1.5s", l:"Response" }].map(({ v, l }) => (
                    <div key={l} style={{ padding:"6px 14px", borderRadius:20, border:"1px solid rgba(56,189,248,.18)", background:"rgba(56,189,248,.05)", textAlign:"center" }}>
                      <div style={{ color:"rgba(186,230,253,.88)", fontSize:13, fontWeight:700 }}>{v}</div>
                      <div style={{ color:"rgba(186,230,253,.38)", fontSize:10 }}>{l}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Login panel */}
            <div style={{ width:"100%", maxWidth:418, animation: entered ? "lp-panel 1s cubic-bezier(.16,1,.3,1) .55s both" : "none" }}>
              <div style={{ background:"rgba(8,11,23,.78)", backdropFilter:"blur(26px)", border:"1px solid rgba(56,189,248,.14)", borderRadius:20, padding:"34px 30px", boxShadow:"0 30px 60px rgba(0,0,0,.62), 0 0 0 1px rgba(255,255,255,.03), inset 0 1px 0 rgba(255,255,255,.055)", position:"relative", overflow:"hidden", transform:`translate(${px*-.36}px,${py*-.26}px)`, transition:"transform .16s ease-out" }}>
                <div style={{ position:"absolute", top:0, left:"18%", right:"18%", height:1, background:"linear-gradient(90deg, transparent, rgba(56,189,248,.48), transparent)" }} />
                <div style={{ position:"absolute", top:0, right:0, width:120, height:120, background:"radial-gradient(circle at top right, rgba(99,102,241,.07) 0%, transparent 70%)", pointerEvents:"none" }} />

                <div style={{ marginBottom:26 }}>
                  <h2 style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:21, fontWeight:700, color:"#f0f9ff", margin:0, marginBottom:3 }}>Welcome back</h2>
                  <p style={{ color:"rgba(186,230,253,.42)", fontSize:13, margin:0 }}>Sign in to your workspace</p>
                </div>

                <div style={{ marginBottom:18 }}>
                  <a href={`${API_BASE}/api/auth/oauth/google`} onClick={(e) => handleOAuthClick(e)} className="lp-google">
                    <svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true">
                      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                    </svg>
                    Continue with Google
                  </a>
                </div>

                <div style={{ display:"flex", alignItems:"center", gap:12, marginBottom:18 }}>
                  <div style={{ flex:1, height:1, background:"rgba(255,255,255,.07)" }} />
                  <span style={{ color:"rgba(186,230,253,.28)", fontSize:10, letterSpacing:".12em" }}>OR WITH EMAIL</span>
                  <div style={{ flex:1, height:1, background:"rgba(255,255,255,.07)" }} />
                </div>

                <form onSubmit={handleSubmit} style={{ display:"flex", flexDirection:"column", gap:14 }} noValidate>
                  <div className="lp-field">
                    <label htmlFor="email" className="lp-lbl" style={{ display:"block", color:"rgba(186,230,253,.52)", fontSize:10, fontWeight:600, letterSpacing:".1em", textTransform:"uppercase", marginBottom:6, transition:"color .2s" }}>Email address</label>
                    <input id="email" type="email" autoComplete="email" value={email} onChange={(e) => { setEmail(e.target.value); setErrors((p) => ({ ...p, email: undefined })); }} placeholder="you@example.com" className={`lp-input${errors.email ? " lp-err" : ""}`} />
                    {errors.email && <p style={{ color:"rgba(239,68,68,.85)", fontSize:11, marginTop:4 }}>{errors.email}</p>}
                  </div>

                  <div className="lp-field">
                    <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:6 }}>
                      <label htmlFor="password" className="lp-lbl" style={{ color:"rgba(186,230,253,.52)", fontSize:10, fontWeight:600, letterSpacing:".1em", textTransform:"uppercase", transition:"color .2s" }}>Password</label>
                      <Link to="/forgot-password" style={{ color:"rgba(56,189,248,.65)", fontSize:11, textDecoration:"none" }} onMouseEnter={(e) => { (e.target as HTMLElement).style.color = "rgba(56,189,248,1)"; }} onMouseLeave={(e) => { (e.target as HTMLElement).style.color = "rgba(56,189,248,.65)"; }}>Forgot password?</Link>
                    </div>
                    <div style={{ position:"relative" }}>
                      <input id="password" type={showPassword ? "text" : "password"} autoComplete="current-password" value={password} onChange={(e) => { setPassword(e.target.value); setErrors((p) => ({ ...p, password: undefined })); }} placeholder="••••••••" className={`lp-input${errors.password ? " lp-err" : ""}`} style={{ paddingRight:42 }} />
                      <button type="button" onClick={() => setShowPassword((p) => !p)} aria-label={showPassword ? "Hide password" : "Show password"} style={{ position:"absolute", right:12, top:"50%", transform:"translateY(-50%)", background:"none", border:"none", cursor:"pointer", color:"rgba(186,230,253,.38)", padding:0, display:"flex", alignItems:"center", transition:"color .2s" }} onMouseEnter={(e) => { e.currentTarget.style.color = "rgba(186,230,253,.8)"; }} onMouseLeave={(e) => { e.currentTarget.style.color = "rgba(186,230,253,.38)"; }}>
                        {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                      </button>
                    </div>
                    {errors.password && <p style={{ color:"rgba(239,68,68,.85)", fontSize:11, marginTop:4 }}>{errors.password}</p>}
                  </div>

                  <button id="login-submit-btn" type="submit" disabled={isLoading}
                    style={{ width:"100%", padding:"13px 20px", borderRadius:10, border:"1px solid rgba(56,189,248,.38)", background:"linear-gradient(135deg, rgba(56,189,248,.17) 0%, rgba(99,102,241,.21) 100%)", color:"#e0f2fe", fontSize:14, fontWeight:600, fontFamily:"'Space Grotesk',sans-serif", letterSpacing:".04em", cursor: isLoading ? "not-allowed" : "pointer", opacity: isLoading ? .68 : 1, display:"flex", alignItems:"center", justifyContent:"center", gap:8, transition:"all .2s ease", boxShadow:"0 4px 22px rgba(56,189,248,.13), inset 0 1px 0 rgba(255,255,255,.09)", animation: btnPulse ? "lp-btnpulse .65s ease-out" : "none", backdropFilter:"blur(8px)" }}
                    onMouseEnter={(e) => { if (!isLoading) { const el = e.currentTarget; el.style.background="linear-gradient(135deg, rgba(56,189,248,.27) 0%, rgba(99,102,241,.31) 100%)"; el.style.borderColor="rgba(56,189,248,.62)"; el.style.transform="translateY(-1px)"; el.style.boxShadow="0 8px 28px rgba(56,189,248,.22), inset 0 1px 0 rgba(255,255,255,.14)"; } }}
                    onMouseLeave={(e) => { const el = e.currentTarget; el.style.background="linear-gradient(135deg, rgba(56,189,248,.17) 0%, rgba(99,102,241,.21) 100%)"; el.style.borderColor="rgba(56,189,248,.38)"; el.style.transform="translateY(0)"; el.style.boxShadow="0 4px 22px rgba(56,189,248,.13), inset 0 1px 0 rgba(255,255,255,.09)"; }}
                    onMouseDown={(e) => { e.currentTarget.style.transform = "translateY(0) scale(.985)"; }}
                    onMouseUp={(e) => { e.currentTarget.style.transform = "translateY(-1px) scale(1)"; }}
                  >
                    {isLoading ? (
                      <><Loader2 size={15} style={{ animation:"lp-spin 1s linear infinite" }} /> Authenticating…</>
                    ) : (
                      <><svg width="15" height="15" viewBox="0 0 24 24" fill="none"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4M10 17l5-5-5-5M13.8 12H3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg> Sign In</>
                    )}
                  </button>
                </form>

                <div style={{ marginTop:22, display:"flex", flexDirection:"column", alignItems:"center", gap:11 }}>
                  <p style={{ color:"rgba(186,230,253,.38)", fontSize:13, margin:0 }}>
                    No account?{" "}
                    <Link to="/register" style={{ color:"rgba(56,189,248,.78)", textDecoration:"none", fontWeight:600 }} onMouseEnter={(e) => { (e.target as HTMLElement).style.color = "rgba(56,189,248,1)"; }} onMouseLeave={(e) => { (e.target as HTMLElement).style.color = "rgba(56,189,248,.78)"; }}>Create account →</Link>
                  </p>
                  <button onClick={handleGuest} style={{ background:"rgba(255,255,255,.025)", border:"1px solid rgba(255,255,255,.075)", borderRadius:20, padding:"5px 16px", color:"rgba(186,230,253,.32)", fontSize:12, cursor:"pointer", transition:"all .2s ease", fontFamily:"'Inter',sans-serif" }}
                    onMouseEnter={(e) => { const el = e.currentTarget; el.style.color="rgba(186,230,253,.65)"; el.style.borderColor="rgba(255,255,255,.14)"; el.style.background="rgba(255,255,255,.055)"; }}
                    onMouseLeave={(e) => { const el = e.currentTarget; el.style.color="rgba(186,230,253,.32)"; el.style.borderColor="rgba(255,255,255,.075)"; el.style.background="rgba(255,255,255,.025)"; }}
                  >Continue as guest →</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}