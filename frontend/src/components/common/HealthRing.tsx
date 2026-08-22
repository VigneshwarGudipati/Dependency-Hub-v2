import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface HealthRingProps {
  score: number | null;
  size?: number;
  label?: string;
}

export function HealthRing({ score, size = 160, label = "Health score" }: HealthRingProps) {
  const radius = size / 2 - 12;
  const circumference = 2 * Math.PI * radius;

  const displayScore = score !== null ? score : "N/A";
  const validScore = score !== null ? score : 0;

  const offset = circumference - (validScore / 100) * circumference;
  const tone =
    score === null
      ? "text-muted-foreground"
      : score >= 85
        ? "text-success"
        : score >= 65
          ? "text-warning"
          : "text-destructive";
  const strokeClass = score === null ? "stroke-muted" : "stroke-current";

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            strokeWidth={10}
            className="stroke-muted"
            fill="none"
          />
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            strokeWidth={10}
            strokeLinecap="round"
            className={cn(strokeClass, tone)}
            fill="none"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 1.1, ease: "easeOut" }}
          />
        </svg>
        <div className="absolute inset-0 grid place-items-center">
          <div className="text-center">
            <p className={cn("font-display text-4xl font-bold", tone)}>{displayScore}</p>
            {score !== null && <p className="text-xs text-muted-foreground">/ 100</p>}
          </div>
        </div>
      </div>
      <p className="text-sm font-medium text-muted-foreground">{label}</p>
    </div>
  );
}
