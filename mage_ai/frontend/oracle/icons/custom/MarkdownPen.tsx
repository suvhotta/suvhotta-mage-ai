function MarkdownPen({
  fill = 'white',
  size,
}: {
  fill?: string;
  size: number,
}) {
  return (
    <svg
      fill="none"
      height={size}
      viewBox="0 0 20 21"
      width={size}
      xmlns="http://www.w3.org/2000/svg"
    >
      <g clipPath="url(#clip0_11802_82284)">
        <path
          clipRule="evenodd"
          d="M10 20.0024C15.5228 20.0024 20 15.5253 20 10.0024C20 4.47959 15.5228 0.00244141 10 0.00244141C4.47715 0.00244141 0 4.47959 0 10.0024C0 15.5253 4.47715 20.0024 10 20.0024ZM10 18.5024C11.5782 18.5024 13.0559 18.0723 14.3224 17.323C14.3144 17.3061 14.307 17.2888 14.3002 17.2712L11.5045 10.0024H8.49587L5.70021 17.2712C5.69339 17.2889 5.68596 17.3062 5.67796 17.3231C6.94434 18.0724 8.42195 18.5024 10 18.5024ZM11.6336 6.15938L15.5784 16.416C17.3685 14.8577 18.5 12.5622 18.5 10.0024C18.5 5.30802 14.6944 1.50244 10 1.50244C5.30558 1.50244 1.5 5.30802 1.5 10.0024C1.5 12.5623 2.63162 14.8579 4.4219 16.4163L8.36685 6.15939C8.94212 4.66367 11.0583 4.66367 11.6336 6.15938Z"
          fill={fill}
          fillRule="evenodd"
        />
      </g>
      <defs>
        <clipPath id="clip0_11802_82284">
          <rect
            fill={fill}
            height="20"
            transform="translate(0 0.00244141)"
            width="20"
          />
        </clipPath>
      </defs>
    </svg>
  );
}

export default MarkdownPen;