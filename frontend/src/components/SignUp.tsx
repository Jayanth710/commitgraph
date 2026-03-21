"use client";
import React, { Dispatch, SetStateAction, useState } from "react";
import { Label } from "@/components/ui/label";
import { Input } from "./ui/input";
import { Button } from "./ui/button";
import { cn } from "@/lib/utils";
import { useAuth } from "@/components/AuthProvider";
import { api } from "@/lib/api";
import { toast } from "react-toastify";
import axios from "axios";

type SignUpProps = {
  className?: string;
  setIsLogin: Dispatch<SetStateAction<boolean>>;
  [key: string]: unknown;
};

interface SignUpFormData {
  firstname: string;
  lastname: string;
  email: string;
  password: string;
  re_password: string;
}

function SignUp({ setIsLogin }: SignUpProps) {
  const { login } = useAuth();
  const [data, setData] = useState<SignUpFormData>({
    firstname: "",
    lastname: "",
    email: "",
    password: "",
    re_password: "",
  });

  const onChangeHandler = (e: React.ChangeEvent<HTMLInputElement>) => {
    setData({ ...data, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (data.password !== data.re_password) {
      toast.error("Password and re-password do not match.");
      return;
    }

    if (data.password.length < 6) {
      toast.error("Password must be at least 6 characters.");
      return;
    }

    try {
      const response = await api.signup({
        firstname: data.firstname,
        lastname: data.lastname,
        email: data.email,
        password: data.password,
      });
      toast.success(`${data.email} registration was successful.`);
      login(response.token, response.user);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response) {
        const msg = err.response.data?.detail || err.response.data?.message || "Registration failed";
        if (err.response.status === 409) {
          toast.error("Email already registered. Please log in.");
          setIsLogin(true);
        } else {
          toast.error(msg);
        }
      } else {
        toast.error("An unexpected error occurred. Please try again.");
        console.error(err);
      }
    } finally {
      setData({
        firstname: "",
        lastname: "",
        email: "",
        password: "",
        re_password: "",
      });
    }
  };

  const handleGoogleLogin = () => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    window.location.href = `${apiUrl}/auth/google-signin/start`;
  };

  return (
    <div className="shadow-2xl mx-auto w-full max-w-md rounded-none bg-white p-4 md:rounded-2xl md:p-6 dark:bg-black">
      <h2 className="text-xl font-bold text-neutral-800 dark:text-neutral-200">
        Welcome to CommitGraph
      </h2>
      <p className="mt-1 max-w-sm text-sm text-neutral-600 dark:text-neutral-300">
        Sign up to start tracking your commitments across all your email accounts
      </p>

      <form className="my-6" onSubmit={handleSubmit}>
        <div className="mb-4 flex flex-col space-y-2 md:flex-row md:space-y-0 md:space-x-2">
          <LabelInputContainer>
            <Label htmlFor="firstname">First name</Label>
            <Input id="firstname" placeholder="John" type="text" name="firstname" onChange={onChangeHandler} value={data.firstname} />
          </LabelInputContainer>
          <LabelInputContainer>
            <Label htmlFor="lastname">Last name</Label>
            <Input id="lastname" placeholder="Doe" type="text" name="lastname" onChange={onChangeHandler} value={data.lastname} />
          </LabelInputContainer>
        </div>
        <LabelInputContainer className="mb-4">
          <Label htmlFor="email">Email Address</Label>
          <Input id="email" placeholder="you@example.com" type="email" name="email" onChange={onChangeHandler} value={data.email} required />
        </LabelInputContainer>
        <LabelInputContainer className="mb-4">
          <Label htmlFor="password">Password</Label>
          <Input id="password" placeholder="••••••••" type="password" name="password" onChange={onChangeHandler} value={data.password} required />
        </LabelInputContainer>
        <LabelInputContainer className="mb-4">
          <Label htmlFor="re_password">Re-enter password</Label>
          <Input id="re_password" placeholder="••••••••" type="password" name="re_password" onChange={onChangeHandler} value={data.re_password} required />
        </LabelInputContainer>

        <button
          className="group/btn relative block h-10 w-full rounded-md bg-gradient-to-br from-black to-neutral-600 font-medium text-white shadow-[0px_1px_0px_0px_#ffffff40_inset,0px_-1px_0px_0px_#ffffff40_inset] dark:bg-zinc-800 dark:from-zinc-900 dark:to-zinc-900 dark:shadow-[0px_1px_0px_0px_#27272a_inset,0px_-1px_0px_0px_#27272a_inset] cursor-pointer"
          type="submit"
        >
          Sign up &rarr;
          <BottomGradient />
        </button>

        <div className="my-8 h-[1px] w-full bg-gradient-to-r from-transparent via-neutral-300 to-transparent dark:via-neutral-700" />

        <div className="grid grid-cols-1 gap-4">
          <Button variant="outline" className="w-full cursor-pointer" onClick={handleGoogleLogin} type="button">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" className="h-4 w-4 mr-2">
              <path
                d="M12.48 10.92v3.28h7.84c-.24 1.84-.853 3.187-1.787 4.133-1.147 1.147-2.933 2.4-6.053 2.4-4.827 0-8.6-3.893-8.6-8.72s3.773-8.72 8.6-8.72c2.6 0 4.507 1.027 5.907 2.347l2.307-2.307C18.747 1.44 16.133 0 12.48 0 5.867 0 .307 5.387.307 12s5.56 12 12.173 12c3.573 0 6.267-1.173 8.373-3.36 2.16-2.16 2.84-5.213 2.84-7.667 0-.76-.053-1.467-.173-2.053H12.48z"
                fill="currentColor"
              />
            </svg>
            Continue with Google
          </Button>
        </div>
      </form>
      <div className="text-center text-sm text-black dark:text-white cursor-pointer" onClick={() => setIsLogin(true)}>
        Already have an account?{" "}
        <a href="#" className="underline underline-offset-4">
          Log In
        </a>
      </div>
    </div>
  );
}

const BottomGradient = () => {
  return (
    <>
      <span className="absolute inset-x-0 -bottom-px block h-px w-full bg-gradient-to-r from-transparent via-cyan-500 to-transparent opacity-0 transition duration-500 group-hover/btn:opacity-100" />
      <span className="absolute inset-x-10 -bottom-px mx-auto block h-px w-1/2 bg-gradient-to-r from-transparent via-indigo-500 to-transparent opacity-0 blur-sm transition duration-500 group-hover/btn:opacity-100" />
    </>
  );
};

const LabelInputContainer = ({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) => {
  return (
    <div className={cn("flex w-full flex-col space-y-2", className)}>
      {children}
    </div>
  );
};

export default SignUp;