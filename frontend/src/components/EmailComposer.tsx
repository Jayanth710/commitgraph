"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { Send, X, Loader2 } from "lucide-react";
import { toast } from "react-toastify";

interface EmailComposerProps {
  to: string;
  subject: string;
  threadId?: string;
  accountEmail: string;
  onClose: () => void;
  onSent?: () => void;
}

export default function EmailComposer({
  to,
  subject,
  threadId,
  accountEmail,
  onClose,
  onSent,
}: EmailComposerProps) {
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);

  const replySubject = subject.startsWith("Re:") ? subject : `Re: ${subject}`;

  const handleSend = async () => {
    if (!body.trim()) {
      toast.error("Please write a message.");
      return;
    }

    setSending(true);
    try {
      await api.sendEmail({
        to,
        subject: replySubject,
        body: body.trim(),
        thread_id: threadId,
        account_email: accountEmail,
      });
      toast.success("Email sent!");
      onSent?.();
      onClose();
    } catch (err: any) {
      const msg = err.response?.data?.detail || "Failed to send email";
      toast.error(msg);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-4 mt-3">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex-1">
          <p className="text-xs text-gray-500 dark:text-gray-400">
            To: <span className="text-gray-700 dark:text-gray-300">{to}</span>
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Subject: <span className="text-gray-700 dark:text-gray-300">{replySubject}</span>
          </p>
          <p className="text-xs text-gray-400 dark:text-gray-500">
            From: {accountEmail}
          </p>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        >
          <X size={14} className="text-gray-400" />
        </button>
      </div>

      {/* Body */}
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder="Write your reply..."
        rows={5}
        className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
        autoFocus
      />

      {/* Actions */}
      <div className="flex items-center justify-end gap-2 mt-3">
        <button
          onClick={onClose}
          className="text-xs px-3 py-1.5 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={handleSend}
          disabled={sending || !body.trim()}
          className="flex items-center gap-1.5 text-xs px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          {sending ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
          {sending ? "Sending..." : "Send"}
        </button>
      </div>
    </div>
  );
}