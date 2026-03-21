"use client";
import { Suspense, useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import LogIn from "@/components/LogIn";
import SignUp from "@/components/SignUp";
import { LampDemo } from "@/components/LampEffect";
import { toast } from "react-toastify";

function LoginContent() {
  const [isLogin, setIsLogin] = useState(true);
  const searchParams = useSearchParams();

  useEffect(() => {
    const error = searchParams.get("error");
    if (error) {
      const errorMessages: Record<string, string> = {
        missing_code: "Google sign-in was cancelled.",
        invalid_state: "Security check failed. Please try again.",
        token_exchange_failed: "Could not complete Google sign-in. Please try again.",
        no_access_token: "Google did not return access. Please try again.",
        userinfo_failed: "Could not get your Google profile. Please try again.",
        no_email: "No email found in your Google account.",
        profile_fetch_failed: "Signed in but could not load profile. Please try again.",
        no_token: "Authentication failed. Please try again.",
      };
      toast.error(errorMessages[error] || `Sign-in error: ${error}`);
    }
  }, [searchParams]);

  return (
    <div className="min-h-screen grid grid-cols-1 md:grid-cols-2">
      <div className="hidden md:flex items-center justify-center bg-gray-950">
        <LampDemo />
      </div>
      <div className="flex flex-col justify-center items-center bg-white dark:bg-gray-900 transition-all duration-500">
        {isLogin ? <LogIn setIsLogin={setIsLogin} /> : <SignUp setIsLogin={setIsLogin} />}
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginContent />
    </Suspense>
  );
}