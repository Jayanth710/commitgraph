"use client";
import React from "react";
import { motion } from "motion/react";
import { LampContainer } from "./ui/lamp";
import { Waypoints } from "lucide-react";

export function LampDemo() {
  return (
    <LampContainer>
      <motion.div
        initial={{ opacity: 0.5, y: 100 }}
        whileInView={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3, duration: 0.8, ease: "easeInOut" }}
        className="flex flex-col items-center"
      >
        <Waypoints size={48} className="text-blue-400 mb-6" />
        <h1 className="bg-gradient-to-br from-slate-200 to-slate-400 py-4 bg-clip-text text-center text-5xl font-bold tracking-tight text-transparent">
          CommitGraph
        </h1>
        <p className="bg-gradient-to-br from-slate-300 to-slate-500 bg-clip-text text-center text-lg font-medium tracking-tight text-transparent mt-2 max-w-md">
          Your personal commitment tracking engine.
          <br />
          Never lose a promise across email accounts.
        </p>
      </motion.div>
    </LampContainer>
  );
}