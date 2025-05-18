<script setup lang="ts">
import type { EvalClient } from "@/ts/client";
import { inject, ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();
const client = inject<EvalClient>("client")!;

const username = ref("");
const consent = ref(false);

async function login() {
  try {
    await client.login(username.value);
    router.push({ name: "evaluation" });
  } catch {
    username.value = "";
    consent.value = false;
  }
}
</script>

<template>
  <div class="main container">
    <section class="hero">
      <div class="hero-body">
        <h1 class="title">Welcome to the Passive Agents evaluation!</h1>
        <h2 class="subtitle">Thanks for helping.</h2>
      </div>
    </section>

    <section class="section">
      <h3 class="subtitle">Instructions</h3>
      <div class="content">
        <p>
          In this evaluation, you will be asked to annotate whether a certain suggestion is helpful or not given the
          context of the Starless Lands D&amp;D game. For each annotation, you will be given a short (10-30sec)
          <strong>audio clip</strong>, that audio's <strong>transcript</strong>, and a <strong>suggestion</strong> that
          could possibly aid the Dungeon Master in context. If you cannot determine whether or not the suggestion is
          helpful in the short context given, you can click "get more context" to retrieve earlier parts of gameplay.
        </p>
        <p>
          The suggestions will take one of three forms:
          <ul>
            <li><strong>Gamedata Suggestion</strong>: Referencing the suggested entity in detail would help the DM run
              the game. You will see the details of the suggested entity.
            </li>
            <li><strong>NPC Suggestion</strong>: The DM should show the suggested NPC to the players on screen ("on
              stage"), the suggested NPC should be taken "off stage", or the suggested NPC should be shown saying the
              given speech "on stage".
            </li>
            <li><strong>Suggest Improvised NPC</strong>: The DM does not have a pre-prepared NPC for the current
              scenario, and it would help the DM to randomly generate a new NPC.
            </li>
          </ul>
        </p>
        <div>
          <img src="/interface.png" width="50%" />
        </div>
        <p>
          Once you have listened to the audio and looked at the suggestion, please determine whether it would be helpful
          to the DM. Once you select a label, you will be asked to select any sub-labels that contributed to your
          decision. Finally, you can optionally add additional details about your decision in the comment box.
        </p>
        <p>
          On the left sidebar, you will see a list of multiple sessions you have been assigned to annotate. Please
          complete these in order (top to bottom). Each annotator will be assigned three sessions. Each session should
          take about 1 hour to complete. While annotating, you may wish to reference the player notes (link) to refresh
          your memory on each session's events. You may exit the annotation interface at any time, and your progress
          will be saved.
        </p>
        <p>
          Your responses will be recorded on our annotation server, and the study leads will be able to view your
          responses. Your responses may be released anonymously (with any identifiable information redacted by the
          researchers) individually or in aggregate as part of a research publication.
        </p>
        <p>
          If you have any questions, please contact the study lead.
        </p>
      </div>
    </section>

    <section class="section">
      <h3 class="subtitle">Log In</h3>
      <div class="field">
        <label class="label">Username</label>
        <div class="control">
          <input class="input" type="text" placeholder="username" v-model="username" />
        </div>
        <p class="help">
          This should be your assigned username. Ask the study leads if you are unsure what your login key is.
        </p>
      </div>

      <div class="field">
        <div class="control">
          <label class="checkbox">
            <input type="checkbox" v-model="consent" />
            I agree to participate in this annotation. I understand that my responses will be recorded and may be
            released anonymously.
          </label>
        </div>
      </div>

      <div class="field">
        <div class="control">
          <button class="button is-link" :disabled="!consent" @click="login">Begin</button>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped></style>
