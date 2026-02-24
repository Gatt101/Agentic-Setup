import { z } from "zod";

export const chatMessageSchema = z.object({
  message: z.string().min(1),
});
