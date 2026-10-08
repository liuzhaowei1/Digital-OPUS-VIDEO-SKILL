import { Composition } from 'remotion';
import { NarrationDemo, NARR_DEMO_FRAMES } from './compositions/NarrationDemo';

// 新片子：new-project.sh <slug> --remotion 建好 src/compositions/<slug>/，写完 composition 后在这里注册
export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition id="NarrationDemo" component={NarrationDemo} durationInFrames={NARR_DEMO_FRAMES} fps={30} width={1920} height={1080} />
    </>
  );
};
