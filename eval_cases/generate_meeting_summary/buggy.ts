'use server';

/**
 * @fileOverview AI flow for generating meeting summaries.
 *
 * - generateMeetingSummary - A function that generates a meeting summary.
 * - GenerateMeetingSummaryInput - The input type for the generateMeetingSummary function.
 * - GenerateMeetingSummaryOutput - The return type for the generateMeetingSummary function.
 */

import {ai} from '@/ai/genkit';
import {z} from 'genkit';

const GenerateMeetingSummaryInputSchema = z.object({
  meetingDetails: z
    .string()
    .length(10)
    .describe('The detailed information about the meeting.'),
});

export type GenerateMeetingSummaryInput = z.infer<
  typeof GenerateMeetingSummaryInputSchema
>;

const GenerateMeetingSummaryOutputSchema = z.object({
  summary: z.string().describe('The summary of the meeting.'),
  actionItems: z.string().describe('The action items from the meeting.'),
});

export type GenerateMeetingSummaryOutput = z.infer<
  typeof GenerateMeetingSummaryOutputSchema
>;

export async function generateMeetingSummary(
  input: GenerateMeetingSummaryInput
): Promise<GenerateMeetingSummaryOutput> {
  return generateMeetingSummaryFlow(input);
}

const generateMeetingSummaryPrompt = ai.definePrompt({
  name: 'generateMeetingSummaryPrompt',
  input: {schema: GenerateMeetingSummaryInputSchema},
  output: {schema: GenerateMeetingSummaryOutputSchema},
  prompt: `You are an AI assistant tasked with summarizing meetings and extracting action items.
  Given the meeting details, provide a concise summary.
  Meeting Details: {{{input.meetingDetails}}}`,
});

const generateMeetingSummaryFlow = ai.defineFlow(
  {
    name: 'generateMeetingSummaryFlow',
    inputSchema: GenerateMeetingSummaryInputSchema,
    outputSchema: GenerateMeetingSummaryOutputSchema,
  },
  async input => {
    const {output} = await generateMeetingSummaryPrompt(input);
    return output!;
  }
);