import logo from '../assets/logo-mark.webp';

/* Brand lock-up: logo mark (from assets/logo.png, trimmed and downscaled to
   logo-mark.webp) + wordmark. The mark is pale line art designed for the dark
   forest panels (sidebar, login left side). The image is decorative because
   the wordmark next to it already names the product. */
export default function Brand({ large = false }) {
  const size = large ? 52 : 36;
  return (
    <div className={`brand ${large ? 'brand-large' : ''}`}>
      <img className="brand-symbol" src={logo} alt="" aria-hidden="true" width={size} height={size} draggable="false" />
      <span className="brand-name">verify<span>lens</span><span className="brand-period">.</span></span>
    </div>
  );
}
