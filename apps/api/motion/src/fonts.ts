import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";

// Display font for hero text — never system defaults.
export const fontsReady = Promise.all([
  loadFont({ family: "Poppins", url: staticFile("fonts/Poppins-Bold.ttf"), weight: "700" }),
  loadFont({ family: "Poppins", url: staticFile("fonts/Poppins-ExtraBold.ttf"), weight: "800" }),
]);
