import "./MountainBackdrop.css";

/** Decorative layered ridgeline with a low sun, behind the home screen. */
export function MountainBackdrop() {
  return (
    <svg
      className="de-backdrop"
      viewBox="0 0 1200 520"
      preserveAspectRatio="xMaxYMin slice"
      aria-hidden="true"
    >
      <circle className="de-backdrop__sun" cx="1170" cy="90" r="64" />
      {/* Contour-line hint, like a topo map bleeding through. */}
      <g className="de-backdrop__contours">
        <path d="M-20 250c120-60 220-30 330-70s200-90 330-50 190 70 300 40 180-60 280-20" />
        <path d="M-20 290c130-55 230-25 340-62s210-80 330-45 180 62 290 36 180-52 280-16" />
        <path d="M-20 330c140-48 240-20 350-52s210-70 330-40 170 54 280 32 190-44 280-12" />
      </g>
      <path
        className="de-backdrop__ridge de-backdrop__ridge--far"
        d="M0 360 130 250l70 60 120-150 110 130 80-70 150 150 110-190 120 150 90-80 220 180V520H0z"
      />
      <path
        className="de-backdrop__ridge de-backdrop__ridge--mid"
        d="M0 420 170 320l90 70 150-130 130 120 110-60 170 120 140-150 240 190V520H0z"
      />
      <path
        className="de-backdrop__ridge de-backdrop__ridge--near"
        d="M0 470 220 400l130 50 190-90 160 80 200-60 300 110V520H0z"
      />
    </svg>
  );
}
