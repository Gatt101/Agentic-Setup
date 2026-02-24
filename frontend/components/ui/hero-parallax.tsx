"use client";
import {
    motion,
    useScroll,
    useSpring,
    useTransform,
    type MotionValue,
} from "framer-motion";
import React from "react";

export const HeroParallax = ({
  products,
  header,
}: {
  products: {
    title: string;
    link: string;
    thumbnail: string;
  }[];
  header?: React.ReactNode;
}) => {
  const firstRow = products.slice(0, 5);
  const secondRow = products.slice(5, 10);
  const thirdRow = products.slice(10, 15);
  const ref = React.useRef(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end start"],
  });

  const springConfig = { stiffness: 300, damping: 30, bounce: 100 };

  const translateX = useSpring(
    useTransform(scrollYProgress, [0, 1], [0, 1000]),
    springConfig,
  );
  const translateXReverse = useSpring(
    useTransform(scrollYProgress, [0, 1], [0, -1000]),
    springConfig,
  );
  const rotateX = useSpring(
    useTransform(scrollYProgress, [0, 0.2], [15, 0]),
    springConfig,
  );
  const opacity = useSpring(
    useTransform(scrollYProgress, [0, 0.2], [0.2, 1]),
    springConfig,
  );
  const rotateZ = useSpring(
    useTransform(scrollYProgress, [0, 0.2], [20, 0]),
    springConfig,
  );
  const translateY = useSpring(
    useTransform(scrollYProgress, [0, 0.2], [-700, 500]),
    springConfig,
  );

  return (
    <div
      ref={ref}
      className="h-[280vh] py-32 overflow-hidden antialiased relative flex flex-col self-auto [perspective:1000px] [transform-style:preserve-3d]"
    >
      {header ?? <HeroHeader />}
      <motion.div
        style={{
          rotateX,
          rotateZ,
          translateY,
          opacity,
        }}
      >
        <motion.div className="flex flex-row-reverse space-x-reverse space-x-20 mb-20">
          {firstRow.map((product) => (
            <ProductCard
              product={product}
              translate={translateX}
              key={product.title}
            />
          ))}
        </motion.div>
        <motion.div className="flex flex-row mb-20 space-x-20">
          {secondRow.map((product) => (
            <ProductCard
              product={product}
              translate={translateXReverse}
              key={product.title}
            />
          ))}
        </motion.div>
        <motion.div className="flex flex-row-reverse space-x-reverse space-x-20">
          {thirdRow.map((product) => (
            <ProductCard
              product={product}
              translate={translateX}
              key={product.title}
            />
          ))}
        </motion.div>
      </motion.div>
    </div>
  );
};

export const HeroHeader = () => {
  return (
    <div className="max-w-7xl relative mx-auto py-20 md:py-32 px-6 w-full left-0 top-0">
      <p className="w-fit rounded-full border border-[var(--color-primary)]/30 bg-[var(--color-primary)]/8 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-[var(--color-primary)] mb-6">
        Orthopedic Clinical AI
      </p>
      <h1 className="landing-heading-font text-4xl md:text-7xl font-bold text-slate-900 dark:text-slate-100 leading-tight">
        OrthoAssist
        <span className="block mt-2 text-[var(--color-primary)]">
          AI-Powered Orthopedic <br className="hidden md:block" /> Clinical Platform
        </span>
      </h1>
      <p className="max-w-2xl text-base md:text-xl mt-6 text-slate-600 dark:text-slate-300 leading-relaxed">
        Analyze X-rays, generate structured reports, and guide orthopedic care
        with clinical precision and confidence.
      </p>
    </div>
  );
};

export const ProductCard = ({
  product,
  translate,
}: {
  product: {
    title: string;
    link: string;
    thumbnail: string;
  };
  translate: MotionValue<number>;
}) => {
  return (
    <motion.div
      style={{ x: translate }}
      whileHover={{ y: -20 }}
      key={product.title}
      className="group/product h-96 w-[30rem] relative shrink-0"
    >
      <a href={product.link} className="block group-hover/product:shadow-2xl">
        <img
          src={product.thumbnail}
          height="600"
          width="600"
          className="object-cover object-left-top absolute h-full w-full inset-0 rounded-2xl"
          alt={product.title}
        />
      </a>
      <div className="absolute inset-0 h-full w-full opacity-0 group-hover/product:opacity-80 bg-gradient-to-t from-slate-900 via-slate-900/60 to-transparent pointer-events-none rounded-2xl transition-opacity duration-300" />
      <div className="absolute bottom-0 left-0 right-0 p-5 opacity-0 group-hover/product:opacity-100 transition-opacity duration-300">
        <h2 className="text-white font-semibold text-lg">{product.title}</h2>
      </div>
    </motion.div>
  );
};
