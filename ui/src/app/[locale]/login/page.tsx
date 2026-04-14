"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  Box,
  Button,
  Card,
  Flex,
  Heading,
  Text,
  TextField,
  Callout,
} from "@radix-ui/themes";
import { LockClosedIcon, ExclamationTriangleIcon } from "@radix-ui/react-icons";

/**
 * Login page — single password field for admin access.
 *
 * Phase UI-0: client-side only (stores a token in localStorage).
 * Phase UI-5: validates against the Python backend's `/api/auth` endpoint.
 */
export default function LoginPage() {
  const t = useTranslations("login");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(false);
    setLoading(true);

    try {
      // TODO (Phase UI-5): POST /api/auth with the password.
      // For now, accept any non-empty password and store it as a bearer token.
      if (!password.trim()) {
        setError(true);
        return;
      }
      localStorage.setItem("datronis-token", password);
      window.location.href = "/";
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Flex
      align="center"
      justify="center"
      className="min-h-screen bg-[var(--gray-a2)]"
    >
      <Box className="w-full max-w-sm p-4">
        <Card size="4">
          <form onSubmit={handleSubmit}>
            <Flex direction="column" gap="4">
              <Flex direction="column" align="center" gap="2">
                <Box className="rounded-full bg-[var(--accent-a3)] p-3">
                  <LockClosedIcon width={24} height={24} />
                </Box>
                <Heading size="5">{t("title")}</Heading>
                <Text size="2" color="gray" align="center">
                  {t("description")}
                </Text>
              </Flex>

              {error && (
                <Callout.Root color="red" size="1">
                  <Callout.Icon>
                    <ExclamationTriangleIcon />
                  </Callout.Icon>
                  <Callout.Text>{t("error")}</Callout.Text>
                </Callout.Root>
              )}

              <TextField.Root
                type="password"
                placeholder={t("placeholder")}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                size="3"
                autoFocus
              />

              <Button type="submit" size="3" loading={loading}>
                {t("submit")}
              </Button>
            </Flex>
          </form>
        </Card>
      </Box>
    </Flex>
  );
}
