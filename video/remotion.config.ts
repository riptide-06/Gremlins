import { Config } from '@remotion/cli/config';
import { existsSync } from 'node:fs';

Config.setVideoImageFormat('jpeg');
Config.setOverwriteOutput(true);

// Local Chrome avoids a Headless Shell discovery failure on this Mac.
const chrome = process.env.REMOTION_BROWSER_EXECUTABLE
  ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
if (existsSync(chrome)) Config.setBrowserExecutable(chrome);
