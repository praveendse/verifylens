import logo from '@/assets/logo-mark.webp';

/** Logo mark + wordmark. The image is decorative: the wordmark already names the product. */
export function Brand({ large = false }: { large?: boolean }) {
  const size = large ? 52 : 36;
  return (
    <div className={`brand ${large ? 'brand-large' : ''}`}>
      <img
        className="brand-symbol"
        src={logo}
        alt=""
        aria-hidden="true"
        width={size}
        height={size}
        draggable="false"
      />
      <span className="brand-name">
        verify<span>lens</span>
        <span className="brand-period">.</span>
      </span>
    </div>
  );
}
